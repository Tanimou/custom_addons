# -*- coding: utf-8 -*-

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'supplier_approval')
class TestSupplierEvaluation(TransactionCase):
    """Test supplier evaluation score calculations and validations"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test user
        cls.purchase_user = cls.env['res.users'].create({
            'name': 'Evaluator Test',
            'login': 'evaluator_test',
            'email': 'evaluator@test.com',
            'groups_id': [(6, 0, [cls.env.ref('purchase.group_purchase_user').id])]
        })
        
        # Create test supplier
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Test Supplier XYZ',
            'email': 'supplier@test.com',
            'supplier_rank': 1,
            'is_company': True,
        })
        
        # Create test purchase order
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        cls.purchase_order = cls.env['purchase.order'].create({
            'partner_id': cls.supplier.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_qty': 10,
                'price_unit': 100,
            })],
        })

    def test_01_create_evaluation(self):
        """Test creating a supplier evaluation"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
        })
        
        self.assertEqual(evaluation.partner_id, self.supplier, "Supplier should be set")
        self.assertEqual(evaluation.evaluated_by, self.purchase_user, "Evaluated by should be current user")
        self.assertTrue(evaluation.name, "Name should be auto-generated")

    def test_02_overall_score_calculation(self):
        """Test weighted average calculation for overall score"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 80,      # 30% weight = 24 points
            'delivery_score': 70,     # 25% weight = 17.5 points
            'reactivity_score': 60,   # 20% weight = 12 points
            'compliance_score': 90,   # 15% weight = 13.5 points
            'relationship_score': 100, # 10% weight = 10 points
        })
        
        # Expected: 24 + 17.5 + 12 + 13.5 + 10 = 77.0
        expected_score = 77.0
        
        self.assertAlmostEqual(
            evaluation.overall_score, 
            expected_score, 
            places=1, 
            msg="Overall score should be weighted average"
        )

    def test_03_overall_score_calculation_edge_cases(self):
        """Test score calculation with edge values"""
        # Test with all zeros
        evaluation_zeros = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 0,
            'delivery_score': 0,
            'reactivity_score': 0,
            'compliance_score': 0,
            'relationship_score': 0,
        })
        
        self.assertEqual(evaluation_zeros.overall_score, 0.0, "All zeros should result in 0 score")
        
        # Test with all 100s
        evaluation_perfect = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 100,
            'delivery_score': 100,
            'reactivity_score': 100,
            'compliance_score': 100,
            'relationship_score': 100,
        })
        
        self.assertEqual(evaluation_perfect.overall_score, 100.0, "All 100s should result in 100 score")

    def test_04_score_range_constraint(self):
        """Test that scores must be between 0 and 100"""
        # Test score > 100
        with self.assertRaises(ValidationError):
            self.env['supplier.evaluation'].with_user(self.purchase_user).create({
                'partner_id': self.supplier.id,
                'evaluation_date': date.today(),
                'quality_score': 110,  # Invalid
                'delivery_score': 80,
                'reactivity_score': 70,
                'compliance_score': 85,
                'relationship_score': 90,
            })
        
        # Test negative score
        with self.assertRaises(ValidationError):
            self.env['supplier.evaluation'].with_user(self.purchase_user).create({
                'partner_id': self.supplier.id,
                'evaluation_date': date.today(),
                'quality_score': 80,
                'delivery_score': -10,  # Invalid
                'reactivity_score': 70,
                'compliance_score': 85,
                'relationship_score': 90,
            })

    def test_05_evaluation_date_constraint(self):
        """Test that evaluation date cannot be in the future"""
        tomorrow = date.today() + timedelta(days=1)
        
        with self.assertRaises(ValidationError):
            self.env['supplier.evaluation'].with_user(self.purchase_user).create({
                'partner_id': self.supplier.id,
                'evaluation_date': tomorrow,  # Future date - invalid
                'quality_score': 80,
                'delivery_score': 75,
                'reactivity_score': 70,
                'compliance_score': 85,
                'relationship_score': 90,
            })

    def test_06_partner_required(self):
        """Test that partner_id is required"""
        with self.assertRaises(ValidationError):
            self.env['supplier.evaluation'].with_user(self.purchase_user).create({
                'evaluation_date': date.today(),
                'quality_score': 80,
                'delivery_score': 75,
                'reactivity_score': 70,
                'compliance_score': 85,
                'relationship_score': 90,
                # partner_id missing
            })

    def test_07_name_generation(self):
        """Test that name field is auto-generated with correct format"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date(2024, 3, 15),
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
        })
        
        # Name should be: "[Supplier Name] - [Date]"
        self.assertIn(self.supplier.name, evaluation.name, "Name should include supplier name")
        self.assertIn('2024-03-15', evaluation.name, "Name should include evaluation date")

    def test_08_purchase_order_link(self):
        """Test linking evaluation to purchase order"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'purchase_order_id': self.purchase_order.id,
            'evaluation_date': date.today(),
            'quality_score': 85,
            'delivery_score': 80,
            'reactivity_score': 75,
            'compliance_score': 90,
            'relationship_score': 85,
        })
        
        self.assertEqual(evaluation.purchase_order_id, self.purchase_order, "PO should be linked")

    def test_09_multiple_evaluations_same_supplier(self):
        """Test creating multiple evaluations for the same supplier"""
        evaluation1 = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today() - timedelta(days=30),
            'quality_score': 70,
            'delivery_score': 65,
            'reactivity_score': 60,
            'compliance_score': 75,
            'relationship_score': 80,
        })
        
        evaluation2 = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 85,
            'delivery_score': 80,
            'reactivity_score': 75,
            'compliance_score': 90,
            'relationship_score': 85,
        })
        
        self.assertNotEqual(evaluation1.overall_score, evaluation2.overall_score, 
                           "Different evaluations should have different scores")
        
        # Check supplier has both evaluations
        supplier_evals = self.env['supplier.evaluation'].search([
            ('partner_id', '=', self.supplier.id)
        ])
        self.assertGreaterEqual(len(supplier_evals), 2, "Supplier should have multiple evaluations")

    def test_10_weighted_calculation_precision(self):
        """Test that weighted calculation maintains precision"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 77,      # 30% = 23.1
            'delivery_score': 83,     # 25% = 20.75
            'reactivity_score': 66,   # 20% = 13.2
            'compliance_score': 94,   # 15% = 14.1
            'relationship_score': 59, # 10% = 5.9
        })
        
        # Expected: 23.1 + 20.75 + 13.2 + 14.1 + 5.9 = 77.05
        expected_score = 77.05
        
        self.assertAlmostEqual(
            evaluation.overall_score, 
            expected_score, 
            places=2, 
            msg="Weighted calculation should maintain precision"
        )

    def test_11_comments_field(self):
        """Test that comments can be added to evaluation"""
        evaluation = self.env['supplier.evaluation'].with_user(self.purchase_user).create({
            'partner_id': self.supplier.id,
            'evaluation_date': date.today(),
            'quality_score': 80,
            'delivery_score': 75,
            'reactivity_score': 70,
            'compliance_score': 85,
            'relationship_score': 90,
            'comments': 'Good supplier, minor delays observed.',
        })
        
        self.assertEqual(evaluation.comments, 'Good supplier, minor delays observed.',
                        "Comments should be saved")

    def test_12_evaluation_history_tracking(self):
        """Test tracking evaluation history over time"""
        dates = [
            date.today() - timedelta(days=90),
            date.today() - timedelta(days=60),
            date.today() - timedelta(days=30),
            date.today(),
        ]
        
        scores = [60, 70, 80, 85]
        
        for eval_date, score in zip(dates, scores):
            self.env['supplier.evaluation'].with_user(self.purchase_user).create({
                'partner_id': self.supplier.id,
                'evaluation_date': eval_date,
                'quality_score': score,
                'delivery_score': score,
                'reactivity_score': score,
                'compliance_score': score,
                'relationship_score': score,
            })
        
        # Get all evaluations sorted by date
        evaluations = self.env['supplier.evaluation'].search([
            ('partner_id', '=', self.supplier.id)
        ], order='evaluation_date asc')
        
        self.assertGreaterEqual(len(evaluations), 4, "Should have all evaluations")
        
        # Verify score improvement trend
        previous_score = 0
        for evaluation in evaluations:
            self.assertGreaterEqual(evaluation.overall_score, previous_score,
                                   "Scores should show improvement trend")
            previous_score = evaluation.overall_score
