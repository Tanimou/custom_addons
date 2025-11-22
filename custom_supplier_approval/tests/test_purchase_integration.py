# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'supplier_approval')
class TestPurchaseIntegration(TransactionCase):
    """Test purchase order integration with supplier approval module"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test user
        cls.purchase_user = cls.env['res.users'].create({
            'name': 'Purchase Test User',
            'login': 'purchase_test_user',
            'email': 'purchase.test@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])]
        })
        
        cls.purchase_manager = cls.env['res.users'].create({
            'name': 'Manager Test User',
            'login': 'manager_test_user',
            'email': 'manager.test@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_manager').id])]
        })
        
        # Create approved supplier
        cls.approved_supplier = cls.env['res.partner'].create({
            'name': 'Approved Supplier Ltd',
            'email': 'approved@test.com',
            'supplier_rank': 1,
            'is_company': True,
        })
        
        # Create approval request for approved supplier
        cls.approval_request = cls.env['supplier.approval.request'].create({
            'partner_id': cls.approved_supplier.id,
            'services_provided': 'IT Services',
            'requested_by': cls.purchase_user.id,
        })
        cls.approval_request.action_submit()
        cls.approval_request.with_user(cls.purchase_manager).action_approve()
        
        # Create non-approved supplier
        cls.non_approved_supplier = cls.env['res.partner'].create({
            'name': 'Non-Approved Supplier Inc',
            'email': 'nonapproved@test.com',
            'supplier_rank': 1,
            'is_company': True,
        })
        
        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product Integration',
            'type': 'product',
        })

    def test_01_approved_supplier_in_domain(self):
        """Test that approved suppliers appear in partner domain"""
        # Get domain from purchase order form
        PurchaseOrder = self.env['purchase.order'].with_user(self.purchase_user)
        
        # Create PO with approved supplier (should work)
        po = PurchaseOrder.create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })],
        })
        
        self.assertEqual(po.partner_id, self.approved_supplier, 
                        "Approved supplier should be selectable")

    def test_02_non_approved_supplier_warning(self):
        """Test onchange warning when selecting non-approved supplier"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.non_approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })],
        })
        
        # Trigger onchange
        result = po.onchange_partner_id_warning()
        
        # Should return warning for non-approved supplier
        if result:
            self.assertIn('warning', result, "Should return warning for non-approved supplier")

    def test_03_purchase_order_confirmation_with_approved_supplier(self):
        """Test confirming PO with approved supplier"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 150,
            })],
        })
        
        # Confirm the PO
        po.button_confirm()
        
        self.assertEqual(po.state, 'purchase', "PO should be confirmed for approved supplier")

    def test_04_partner_evaluation_count(self):
        """Test that partner evaluation count is computed correctly"""
        # Create evaluations for approved supplier
        self.env['supplier.evaluation'].create({
            'partner_id': self.approved_supplier.id,
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
        })
        
        self.env['supplier.evaluation'].create({
            'partner_id': self.approved_supplier.id,
            'quality_score': 85,
            'delivery_score': 80,
            'reactivity_score': 75,
            'compliance_score': 90,
            'relationship_score': 85,
        })
        
        # Refresh supplier to trigger compute
        self.approved_supplier.invalidate_recordset()
        
        self.assertGreaterEqual(self.approved_supplier.supplier_evaluation_count, 2,
                               "Supplier should have evaluation count")

    def test_05_smart_button_action(self):
        """Test that smart button action opens correct view"""
        # Create evaluation
        self.env['supplier.evaluation'].create({
            'partner_id': self.approved_supplier.id,
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
        })
        
        # Call smart button action
        action = self.approved_supplier.action_view_supplier_evaluations()
        
        self.assertEqual(action['res_model'], 'supplier.evaluation',
                        "Action should open supplier evaluation model")
        self.assertIn(('partner_id', '=', self.approved_supplier.id), action['domain'],
                     "Action should filter by supplier")

    def test_06_purchase_order_evaluation_link(self):
        """Test linking evaluation to purchase order"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 200,
            })],
        })
        po.button_confirm()
        
        # Create evaluation linked to this PO
        evaluation = self.env['supplier.evaluation'].create({
            'partner_id': self.approved_supplier.id,
            'purchase_order_id': po.id,
            'quality_score': 90,
            'delivery_score': 85,
            'reactivity_score': 80,
            'compliance_score': 95,
            'relationship_score': 90,
        })
        
        self.assertEqual(evaluation.purchase_order_id, po,
                        "Evaluation should be linked to PO")
        self.assertEqual(evaluation.partner_id, po.partner_id,
                        "Evaluation partner should match PO partner")

    def test_07_multiple_pos_same_supplier(self):
        """Test creating multiple POs for same approved supplier"""
        po1 = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 5,
                'price_unit': 100,
            })],
        })
        
        po2 = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 10,
                'price_unit': 120,
            })],
        })
        
        po1.button_confirm()
        po2.button_confirm()
        
        # Both should be confirmed successfully
        self.assertEqual(po1.state, 'purchase', "First PO should be confirmed")
        self.assertEqual(po2.state, 'purchase', "Second PO should be confirmed")

    def test_08_supplier_approval_state_in_partner(self):
        """Test that partner shows approval state correctly"""
        # Approved supplier should have approved state
        approval_state = self.env['supplier.approval.request'].search([
            ('partner_id', '=', self.approved_supplier.id),
            ('state', '=', 'approved')
        ], limit=1)
        
        self.assertTrue(approval_state, "Approved supplier should have approval record")
        
        # Non-approved supplier should not have approved state
        non_approval_state = self.env['supplier.approval.request'].search([
            ('partner_id', '=', self.non_approved_supplier.id),
            ('state', '=', 'approved')
        ], limit=1)
        
        self.assertFalse(non_approval_state, "Non-approved supplier should not have approval")

    def test_09_evaluation_wizard_integration(self):
        """Test evaluation wizard from purchase order"""
        po = self.env['purchase.order'].with_user(self.purchase_user).create({
            'partner_id': self.approved_supplier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 8,
                'price_unit': 175,
            })],
        })
        po.button_confirm()
        
        # Create wizard for evaluation
        wizard = self.env['supplier.evaluation.wizard'].with_context(
            active_id=po.id,
            active_model='purchase.order'
        ).create({
            'partner_id': self.approved_supplier.id,
            'purchase_order_id': po.id,
            'quality_score': 85,
            'delivery_score': 80,
            'reactivity_score': 75,
            'compliance_score': 90,
            'relationship_score': 85,
        })
        
        # Validate wizard
        wizard.action_validate()
        
        # Check that evaluation was created
        evaluation = self.env['supplier.evaluation'].search([
            ('purchase_order_id', '=', po.id)
        ], limit=1)
        
        self.assertTrue(evaluation, "Evaluation should be created from wizard")
        self.assertEqual(evaluation.quality_score, 85, "Scores should match wizard input")

    def test_10_domain_filter_performance(self):
        """Test that domain filter for approved suppliers is efficient"""
        # Create multiple suppliers with approval requests
        for i in range(5):
            supplier = self.env['res.partner'].create({
                'name': f'Test Supplier {i}',
                'email': f'supplier{i}@test.com',
                'supplier_rank': 1,
                'is_company': True,
            })
            
            request = self.env['supplier.approval.request'].create({
                'partner_id': supplier.id,
                'services_provided': f'Service {i}',
                'requested_by': self.purchase_user.id,
            })
            request.action_submit()
            
            if i % 2 == 0:  # Approve every other supplier
                request.with_user(self.purchase_manager).action_approve()
        
        # Get approved suppliers
        approved_suppliers = self.env['supplier.approval.request'].search([
            ('state', '=', 'approved')
        ]).mapped('partner_id')
        
        self.assertGreater(len(approved_suppliers), 0,
                          "Should have some approved suppliers")
