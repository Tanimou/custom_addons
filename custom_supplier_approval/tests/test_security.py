# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'supplier_approval')
class TestSecurityRules(TransactionCase):
    """Test security access control and record rules"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test users with different access levels
        cls.purchase_user1 = cls.env['res.users'].create({
            'name': 'Purchase User 1',
            'login': 'purchase_user1',
            'email': 'user1@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])]
        })
        
        cls.purchase_user2 = cls.env['res.users'].create({
            'name': 'Purchase User 2',
            'login': 'purchase_user2',
            'email': 'user2@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])]
        })
        
        cls.purchase_manager = cls.env['res.users'].create({
            'name': 'Purchase Manager',
            'login': 'purchase_manager',
            'email': 'manager@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_manager').id])]
        })
        
        # Create test supplier
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Security Test Supplier',
            'email': 'security@test.com',
            'supplier_rank': 1,
            'is_company': True,
        })

    def test_01_user_can_read_all_requests(self):
        """Test that purchase users can read all approval requests"""
        # User 1 creates a request
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Security Test',
        })
        
        # User 2 should be able to read it
        request_as_user2 = self.env['supplier.approval.request'].with_user(self.purchase_user2).browse(request.id)
        self.assertTrue(request_as_user2.exists(), "User 2 should be able to read User 1's request")
        self.assertEqual(request_as_user2.partner_id, self.supplier,
                        "User 2 should see correct data")

    def test_02_user_can_create_own_request(self):
        """Test that purchase users can create their own requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Create Test',
        })
        
        self.assertTrue(request.exists(), "User should be able to create request")
        self.assertEqual(request.requested_by, self.purchase_user1,
                        "Requested by should be current user")

    def test_03_user_can_write_own_draft_request(self):
        """Test that purchase users can modify their own draft requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Original Service',
        })
        
        # User 1 should be able to modify their own draft
        request.with_user(self.purchase_user1).write({
            'services_provided': 'Updated Service'
        })
        
        self.assertEqual(request.services_provided, 'Updated Service',
                        "User should be able to update own draft")

    def test_04_user_cannot_write_others_draft_request(self):
        """Test that purchase users cannot modify others' draft requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'User 1 Request',
        })
        
        # User 2 should NOT be able to modify User 1's draft
        with self.assertRaises(AccessError):
            request.with_user(self.purchase_user2).write({
                'services_provided': 'User 2 Trying to Modify'
            })

    def test_05_user_cannot_approve_request(self):
        """Test that regular users cannot approve requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Approval Test',
        })
        request.action_submit()
        
        # Regular user should NOT be able to approve
        with self.assertRaises(AccessError):
            request.with_user(self.purchase_user1).action_approve()

    def test_06_manager_can_approve_request(self):
        """Test that managers can approve any request"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Manager Approval Test',
        })
        request.action_submit()
        
        # Manager should be able to approve
        request.with_user(self.purchase_manager).action_approve()
        
        self.assertEqual(request.state, 'approved', "Manager should be able to approve")

    def test_07_manager_can_reject_request(self):
        """Test that managers can reject requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Manager Rejection Test',
        })
        request.action_submit()
        
        # Manager should be able to reject
        request.with_user(self.purchase_manager).write({
            'rejection_reason': 'Security test rejection'
        })
        request.with_user(self.purchase_manager).action_reject()
        
        self.assertEqual(request.state, 'rejected', "Manager should be able to reject")

    def test_08_user_cannot_reject_request(self):
        """Test that regular users cannot reject requests"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'User Rejection Test',
        })
        request.action_submit()
        
        # User should NOT be able to reject
        with self.assertRaises(AccessError):
            request.with_user(self.purchase_user2).write({
                'rejection_reason': 'Unauthorized rejection'
            })
            request.with_user(self.purchase_user2).action_reject()

    def test_09_sudo_usage_in_workflow(self):
        """Test that sudo() is used correctly in workflow methods"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Sudo Test',
        })
        
        # Submit should work (uses sudo internally for state change)
        request.action_submit()
        self.assertEqual(request.state, 'pending', "Submit should use sudo correctly")
        
        # Approve as manager (uses sudo internally)
        request.with_user(self.purchase_manager).action_approve()
        self.assertEqual(request.state, 'approved', "Approve should use sudo correctly")

    def test_10_manager_can_write_all_states(self):
        """Test that managers can modify requests in any state"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Manager Write Test',
        })
        
        # Submit
        request.action_submit()
        
        # Manager should be able to modify pending request
        request.with_user(self.purchase_manager).write({
            'comments': 'Manager can modify pending'
        })
        
        # Approve
        request.with_user(self.purchase_manager).action_approve()
        
        # Manager should be able to modify approved request
        request.with_user(self.purchase_manager).write({
            'comments': 'Manager can modify approved'
        })
        
        self.assertEqual(request.comments, 'Manager can modify approved',
                        "Manager should be able to modify in any state")

    def test_11_evaluation_access_control(self):
        """Test that evaluation security follows same pattern"""
        # User 1 creates evaluation
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
        })
        
        # User 2 should be able to read
        eval_as_user2 = self.env['supplier.evaluation'].with_user(self.purchase_user2).browse(evaluation.id)
        self.assertTrue(eval_as_user2.exists(), "User 2 should be able to read evaluation")
        
        # User 1 should be able to modify their own
        evaluation.with_user(self.purchase_user1).write({
            'comments': 'Updated by creator'
        })
        
        self.assertEqual(evaluation.comments, 'Updated by creator',
                        "User should be able to update own evaluation")

    def test_12_legal_document_access(self):
        """Test that legal documents follow request access rules"""
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Document Access Test',
        })
        
        # Add legal document
        doc = self.env['supplier.legal.document'].with_user(self.purchase_user1).create({
            'approval_request_id': request.id,
            'document_type': 'Insurance',
            'document_number': 'INS-001',
        })
        
        # User 2 should be able to read document
        doc_as_user2 = self.env['supplier.legal.document'].with_user(self.purchase_user2).browse(doc.id)
        self.assertTrue(doc_as_user2.exists(), "User 2 should be able to read document")

    def test_13_record_rule_for_draft_ownership(self):
        """Test that record rules enforce draft ownership correctly"""
        # User 1 creates draft
        request1 = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Draft 1',
        })
        
        # User 2 creates draft
        request2 = self.env['supplier.approval.request'].with_user(self.purchase_user2).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Draft 2',
        })
        
        # User 1 can write to their draft
        request1.with_user(self.purchase_user1).write({'comments': 'User 1 comment'})
        
        # User 1 cannot write to User 2's draft
        with self.assertRaises(AccessError):
            request2.with_user(self.purchase_user1).write({'comments': 'Unauthorized'})

    def test_14_manager_bypass_record_rules(self):
        """Test that managers can bypass record rules"""
        # User 1 creates draft
        request = self.env['supplier.approval.request'].with_user(self.purchase_user1).create({
            'partner_id': self.supplier.id,
            'services_provided': 'Manager Bypass Test',
        })
        
        # Manager should be able to modify User 1's draft
        request.with_user(self.purchase_manager).write({
            'comments': 'Manager modified user draft'
        })
        
        self.assertEqual(request.comments, 'Manager modified user draft',
                        "Manager should bypass record rules")

    def test_15_acl_csv_coverage(self):
        """Test that ACL definitions cover all models"""
        # Check that access rights exist for main models
        models_to_check = [
            'supplier.approval.request',
            'supplier.evaluation',
            'supplier.legal.document',
            'supplier.evaluation.wizard',
        ]
        
        for model_name in models_to_check:
            # Check user access
            user_access = self.env['ir.model.access'].search([
                ('model_id.model', '=', model_name),
                ('group_id', '=', self.env.ref('purchase.group_purchase_user').id)
            ])
            
            self.assertTrue(user_access, f"User access should exist for {model_name}")
            
            # Check manager access
            manager_access = self.env['ir.model.access'].search([
                ('model_id.model', '=', model_name),
                ('group_id', '=', self.env.ref('purchase.group_purchase_manager').id)
            ])
            
            self.assertTrue(manager_access, f"Manager access should exist for {model_name}")
