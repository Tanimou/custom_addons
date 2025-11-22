# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'supplier_approval')
class TestSupplierApprovalRequest(TransactionCase):
    """Test supplier approval request workflow and business logic"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test users
        cls.purchase_user = cls.env['res.users'].create({
            'name': 'Purchase User Test',
            'login': 'purchase_user_test',
            'email': 'purchase.user@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])]
        })
        
        cls.purchase_manager = cls.env['res.users'].create({
            'name': 'Purchase Manager Test',
            'login': 'purchase_manager_test',
            'email': 'purchase.manager@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_manager').id])]
        })
        
        # Create test supplier (partner)
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Test Supplier ABC',
            'email': 'supplier@test.com',
            'phone': '+33123456789',
            'supplier_rank': 1,
            'is_company': True,
        })
        
        # Create test legal document type
        cls.doc_type = cls.env['supplier.legal.document'].create({
            'name': 'Test Document Type',
        })

    def test_01_create_approval_request(self):
        """Test creating an approval request in draft state"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'IT Equipment',
            'comments': 'Test request',
        })
        
        self.assertEqual(request.state, 'draft', "New request should be in draft state")
        self.assertEqual(request.requested_by, self.purchase_user, "Requested by should be current user")
        self.assertEqual(request.request_date, date.today(), "Request date should be today")
        self.assertTrue(request.name, "Request name should be auto-generated")
        self.assertIn('SAR', request.name, "Request name should contain SAR prefix")

    def test_02_submit_approval_request(self):
        """Test submitting an approval request (draft → pending)"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Software Development',
        })
        
        # Submit the request
        request.action_submit()
        
        self.assertEqual(request.state, 'pending', "Request should be in pending state after submission")
        
        # Check that activities were created for purchase managers
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'supplier.approval.request'),
            ('res_id', '=', request.id),
        ])
        self.assertTrue(activities, "Activities should be created for managers")

    def test_03_submit_without_partner(self):
        """Test that submission fails without a partner"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'services_provided': 'Testing',
        })
        
        with self.assertRaises(ValidationError):
            request.action_submit()

    def test_04_approve_request_as_manager(self):
        """Test approving a request as purchase manager"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Consulting',
        })
        request.action_submit()
        
        # Approve as manager
        request.with_user(self.purchase_manager).action_approve()
        
        self.assertEqual(request.state, 'approved', "Request should be approved")
        self.assertEqual(request.approved_by, self.purchase_manager, "Approved by should be manager")
        self.assertEqual(request.approval_date, date.today(), "Approval date should be today")

    def test_05_approve_request_as_user_fails(self):
        """Test that regular user cannot approve request"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Hardware',
        })
        request.action_submit()
        
        # Attempt to approve as regular user (should fail)
        with self.assertRaises(AccessError):
            request.with_user(self.purchase_user).action_approve()

    def test_06_reject_request_with_reason(self):
        """Test rejecting a request with a reason"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Logistics',
        })
        request.action_submit()
        
        # Reject as manager with reason
        request.with_user(self.purchase_manager).write({'rejection_reason': 'Missing documents'})
        request.with_user(self.purchase_manager).action_reject()
        
        self.assertEqual(request.state, 'rejected', "Request should be rejected")
        self.assertEqual(request.rejection_reason, 'Missing documents', "Rejection reason should be saved")

    def test_07_reject_without_reason_fails(self):
        """Test that rejection fails without a reason"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Transport',
        })
        request.action_submit()
        
        # Attempt to reject without reason (should fail)
        with self.assertRaises(UserError):
            request.with_user(self.purchase_manager).action_reject()

    def test_08_reset_to_draft(self):
        """Test resetting a rejected request to draft"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Manufacturing',
        })
        request.action_submit()
        
        # Reject
        request.with_user(self.purchase_manager).write({'rejection_reason': 'Test rejection'})
        request.with_user(self.purchase_manager).action_reject()
        
        # Reset to draft
        request.action_reset_to_draft()
        
        self.assertEqual(request.state, 'draft', "Request should be back in draft")
        self.assertFalse(request.rejection_reason, "Rejection reason should be cleared")
        self.assertFalse(request.approved_by, "Approved by should be cleared")

    def test_09_workflow_state_transitions(self):
        """Test that only valid state transitions are allowed"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'service_types': 'Design',
        })
        
        # Cannot approve draft request
        with self.assertRaises(UserError):
            request.with_user(self.purchase_manager).action_approve()
        
        # Submit to pending
        request.action_submit()
        
        # Cannot submit pending request again
        with self.assertRaises(UserError):
            request.action_submit()

    def test_10_compute_name_field(self):
        """Test that name field is auto-generated correctly"""
        request1 = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'service_types': 'Test 1',
        })
        
        request2 = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'service_types': 'Test 2',
        })
        
        self.assertTrue(request1.name, "Name should be generated")
        self.assertTrue(request2.name, "Name should be generated")
        self.assertNotEqual(request1.name, request2.name, "Names should be unique")

    def test_11_legal_documents_relationship(self):
        """Test adding legal documents to approval request"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'service_types': 'Legal Testing',
        })
        
        # Add legal document
        doc = self.env['supplier.legal.document'].create({
            'approval_request_id': request.id,
            'document_type': 'Insurance Certificate',
            'document_number': 'INS-2024-001',
            'issue_date': date.today(),
            'expiry_date': date(2025, 12, 31),
        })
        
        self.assertIn(doc, request.legal_document_ids, "Document should be linked to request")
        self.assertEqual(len(request.legal_document_ids), 1, "Should have one document")

    def test_12_message_tracking(self):
        """Test that mail thread is properly tracking changes"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Message Testing',
        })
        
        # Submit and check messages
        request.action_submit()
        
        messages = request.message_ids
        self.assertTrue(messages, "Should have messages in chatter")
