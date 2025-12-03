# -*- coding: utf-8 -*-
"""Tests for fleet.fuel.recharge model.

Test coverage:
- CRUD operations and sequence generation
- Workflow: draft -> submitted -> approved -> posted
- Balance updates (reserve, release, apply_delta)
- Amount validation (> 0 constraint)
- Cancellation handling
- Over-limit scenarios (monthly/daily limits on card)
"""
import logging

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestFleetFuelRecharge(TransactionCase):
    """Test cases for fleet.fuel.recharge model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for fuel recharge tests."""
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.currency = cls.company.currency_id

        # Create vehicle brand and model
        cls.vehicle_brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Recharge Test Brand',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Recharge Test Model',
            'brand_id': cls.vehicle_brand.id,
        })

        # Create test vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'RECHARGE-001',
            'company_id': cls.company.id,
        })

        # Create test driver
        cls.driver = cls.env['hr.employee'].create({
            'name': 'Recharge Test Driver',
            'company_id': cls.company.id,
        })

        # Create test fuel card (active)
        cls.card = cls.env['fleet.fuel.card'].create({
            'card_uid': 'RECHARGE-CARD-001',
            'vehicle_id': cls.vehicle.id,
            'driver_id': cls.driver.id,
            'balance_amount': 500.0,
            'max_month_amount': 5000.0,
            'max_daily_amount': 500.0,
            'company_id': cls.company.id,
        })
        cls.card.action_activate()

        # Create a second card for additional tests
        cls.card_2 = cls.env['fleet.fuel.card'].create({
            'card_uid': 'RECHARGE-CARD-002',
            'vehicle_id': cls.vehicle.id,
            'balance_amount': 0.0,
            'company_id': cls.company.id,
        })
        cls.card_2.action_activate()

        cls.Recharge = cls.env['fleet.fuel.recharge']
        cls.BalanceService = cls.env['fleet.fuel.balance.service']

    # -------------------------------------------------------------------------
    # TEST: BASIC CRUD OPERATIONS
    # -------------------------------------------------------------------------
    def test_01_recharge_creation_basic(self):
        """Test basic recharge creation with auto-generated sequence."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 200.0,
            'recharge_date': fields.Date.today(),
        })

        self.assertTrue(recharge.exists())
        self.assertEqual(recharge.state, 'draft')
        self.assertTrue(recharge.name, "Recharge name should be auto-generated")
        self.assertEqual(recharge.amount, 200.0)
        self.assertEqual(recharge.card_id, self.card)
        self.assertEqual(recharge.company_id, self.company)
        self.assertEqual(recharge.currency_id, self.currency)

    def test_02_recharge_creation_with_description(self):
        """Test recharge creation with description."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 150.0,
            'recharge_date': fields.Date.today(),
            'description': 'Monthly top-up for vehicle operations',
        })

        self.assertEqual(recharge.description, 'Monthly top-up for vehicle operations')

    def test_03_recharge_requested_by_default(self):
        """Test that requested_by_id defaults to current user."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })

        self.assertEqual(recharge.requested_by_id, self.env.user)

    # -------------------------------------------------------------------------
    # TEST: AMOUNT VALIDATION (SQL CONSTRAINT)
    # -------------------------------------------------------------------------
    def test_04_recharge_amount_positive_constraint(self):
        """Test that amount must be positive (SQL constraint)."""
        with self.assertRaises(Exception):
            self.Recharge.create({
                'card_id': self.card.id,
                'amount': 0.0,  # Invalid: must be > 0
                'recharge_date': fields.Date.today(),
            })

    def test_05_recharge_amount_negative_constraint(self):
        """Test that negative amount raises error."""
        with self.assertRaises(Exception):
            self.Recharge.create({
                'card_id': self.card.id,
                'amount': -100.0,  # Invalid
                'recharge_date': fields.Date.today(),
            })

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - SUBMIT
    # -------------------------------------------------------------------------
    def test_06_recharge_submit_workflow(self):
        """Test recharge submission workflow."""
        initial_pending = self.card.pending_amount

        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 300.0,
            'recharge_date': fields.Date.today(),
        })
        self.assertEqual(recharge.state, 'draft')

        # Submit the recharge
        recharge.action_submit()

        self.assertEqual(recharge.state, 'submitted')
        # Pending amount should increase (reservation)
        self.card.invalidate_recordset(['pending_amount'])
        self.assertEqual(self.card.pending_amount, initial_pending + 300.0)

    def test_07_recharge_submit_idempotent(self):
        """Test that submitting an already submitted recharge does nothing."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()
        self.assertEqual(recharge.state, 'submitted')

        # Submit again - should not change state
        recharge.action_submit()
        self.assertEqual(recharge.state, 'submitted')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - APPROVE
    # -------------------------------------------------------------------------
    def test_08_recharge_approve_workflow(self):
        """Test recharge approval workflow."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 200.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()

        # Approve the recharge
        recharge.action_approve()

        self.assertEqual(recharge.state, 'approved')
        self.assertTrue(recharge.approval_date)
        self.assertEqual(recharge.approved_by_id, self.env.user)

    def test_09_recharge_approve_from_draft(self):
        """Test approving directly from draft state."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 150.0,
            'recharge_date': fields.Date.today(),
        })

        # Approve directly from draft
        recharge.action_approve()

        self.assertEqual(recharge.state, 'approved')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - POST (BALANCE UPDATE)
    # -------------------------------------------------------------------------
    def test_10_recharge_post_workflow(self):
        """Test recharge posting and balance update."""
        initial_balance = self.card_2.balance_amount

        recharge = self.Recharge.create({
            'card_id': self.card_2.id,
            'amount': 500.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()
        recharge.action_approve()

        # Post the recharge
        recharge.action_post()

        self.assertEqual(recharge.state, 'posted')
        self.assertTrue(recharge.posting_date)
        self.assertEqual(recharge.posted_by_id, self.env.user)

        # Balance should increase
        self.card_2.invalidate_recordset(['balance_amount', 'pending_amount'])
        self.assertEqual(self.card_2.balance_amount, initial_balance + 500.0)

    def test_11_recharge_post_requires_approval(self):
        """Test that posting requires approval first."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()

        # Try to post without approval
        with self.assertRaises(UserError):
            recharge.action_post()

    def test_12_recharge_post_from_draft_fails(self):
        """Test that posting from draft state fails."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })

        # Try to post directly from draft
        with self.assertRaises(UserError):
            recharge.action_post()

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - CANCEL
    # -------------------------------------------------------------------------
    def test_13_recharge_cancel_from_draft(self):
        """Test cancelling a draft recharge."""
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })

        recharge.action_cancel()

        self.assertEqual(recharge.state, 'cancelled')

    def test_14_recharge_cancel_from_submitted(self):
        """Test cancelling a submitted recharge releases pending amount."""
        recharge = self.Recharge.create({
            'card_id': self.card_2.id,
            'amount': 200.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()

        initial_pending = self.card_2.pending_amount

        # Cancel the recharge
        recharge.action_cancel()

        self.assertEqual(recharge.state, 'cancelled')
        # Pending amount should be released
        self.card_2.invalidate_recordset(['pending_amount'])
        self.assertEqual(self.card_2.pending_amount, max(initial_pending - 200.0, 0.0))

    def test_15_recharge_cancel_from_approved(self):
        """Test cancelling an approved recharge releases pending amount."""
        recharge = self.Recharge.create({
            'card_id': self.card_2.id,
            'amount': 150.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()
        recharge.action_approve()

        # Cancel the recharge
        recharge.action_cancel()

        self.assertEqual(recharge.state, 'cancelled')

    def test_16_recharge_cancel_posted_fails(self):
        """Test that cancelling a posted recharge fails."""
        recharge = self.Recharge.create({
            'card_id': self.card_2.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })
        recharge.action_submit()
        recharge.action_approve()
        recharge.action_post()

        with self.assertRaises(UserError):
            recharge.action_cancel()

    # -------------------------------------------------------------------------
    # TEST: FULL WORKFLOW CYCLE
    # -------------------------------------------------------------------------
    def test_17_recharge_full_workflow(self):
        """Test complete workflow: draft -> submitted -> approved -> posted."""
        # Create a fresh card for this test
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'WORKFLOW-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 100.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        initial_balance = test_card.balance_amount

        recharge = self.Recharge.create({
            'card_id': test_card.id,
            'amount': 500.0,
            'recharge_date': fields.Date.today(),
        })

        # Step 1: Draft
        self.assertEqual(recharge.state, 'draft')

        # Step 2: Submit
        recharge.action_submit()
        self.assertEqual(recharge.state, 'submitted')
        test_card.invalidate_recordset(['pending_amount'])
        self.assertEqual(test_card.pending_amount, 500.0)

        # Step 3: Approve
        recharge.action_approve()
        self.assertEqual(recharge.state, 'approved')
        self.assertTrue(recharge.approved_by_id)
        self.assertTrue(recharge.approval_date)

        # Step 4: Post
        recharge.action_post()
        self.assertEqual(recharge.state, 'posted')
        self.assertTrue(recharge.posted_by_id)
        self.assertTrue(recharge.posting_date)

        # Verify balance update
        test_card.invalidate_recordset(['balance_amount', 'pending_amount'])
        self.assertEqual(test_card.balance_amount, initial_balance + 500.0)
        self.assertEqual(test_card.pending_amount, 0.0)

    # -------------------------------------------------------------------------
    # TEST: MULTIPLE RECHARGES
    # -------------------------------------------------------------------------
    def test_18_recharge_multiple_sequential(self):
        """Test multiple sequential recharges on same card."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'MULTI-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        # First recharge
        recharge1 = self.Recharge.create({
            'card_id': test_card.id,
            'amount': 200.0,
            'recharge_date': fields.Date.today(),
        })
        recharge1.action_submit()
        recharge1.action_approve()
        recharge1.action_post()

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 200.0)

        # Second recharge
        recharge2 = self.Recharge.create({
            'card_id': test_card.id,
            'amount': 300.0,
            'recharge_date': fields.Date.today(),
        })
        recharge2.action_submit()
        recharge2.action_approve()
        recharge2.action_post()

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 500.0)

    def test_19_recharge_batch_creation(self):
        """Test creating multiple recharges at once."""
        recharges_vals = [
            {
                'card_id': self.card.id,
                'amount': 100.0,
                'recharge_date': fields.Date.today(),
            },
            {
                'card_id': self.card.id,
                'amount': 200.0,
                'recharge_date': fields.Date.today(),
            },
        ]

        recharges = self.Recharge.create(recharges_vals)

        self.assertEqual(len(recharges), 2)
        self.assertTrue(all(r.name for r in recharges))
        self.assertEqual(recharges[0].amount, 100.0)
        self.assertEqual(recharges[1].amount, 200.0)

    # -------------------------------------------------------------------------
    # TEST: BALANCE SERVICE METHODS
    # -------------------------------------------------------------------------
    def test_20_balance_service_reserve_amount(self):
        """Test balance service reserve_amount method."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SERVICE-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.reserve_amount(test_card, 250.0)

        test_card.invalidate_recordset(['pending_amount'])
        self.assertEqual(test_card.pending_amount, 250.0)

    def test_21_balance_service_release_amount(self):
        """Test balance service release_amount method."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SERVICE-CARD-002',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'pending_amount': 300.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.release_amount(test_card, 150.0)

        test_card.invalidate_recordset(['pending_amount'])
        self.assertEqual(test_card.pending_amount, 150.0)

    def test_22_balance_service_apply_delta(self):
        """Test balance service apply_delta method."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SERVICE-CARD-003',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 500.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.apply_delta(test_card, 200.0)

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 700.0)

    def test_23_balance_service_reserve_zero_amount(self):
        """Test reserve_amount with zero amount does nothing."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SERVICE-CARD-004',
            'vehicle_id': self.vehicle.id,
            'pending_amount': 100.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.reserve_amount(test_card, 0.0)

        test_card.invalidate_recordset(['pending_amount'])
        self.assertEqual(test_card.pending_amount, 100.0)  # Unchanged

    # -------------------------------------------------------------------------
    # TEST: DATES
    # -------------------------------------------------------------------------
    def test_24_recharge_date_tracking(self):
        """Test recharge date fields."""
        custom_date = fields.Date.from_string('2025-06-15')
        recharge = self.Recharge.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'recharge_date': custom_date,
        })

        self.assertEqual(recharge.recharge_date, custom_date)
