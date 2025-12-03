# -*- coding: utf-8 -*-
"""Tests for fleet.fuel.expense model.

Test coverage:
- CRUD operations and sequence generation
- Workflow: draft -> submitted -> validated / rejected
- Balance deduction on validation
- Insufficient balance blocking
- Odometer validation (positive values)
- Receipt attachment constraint
- Price per liter computation
- Card/vehicle company constraints
"""
import base64
import logging

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestFleetFuelExpense(TransactionCase):
    """Test cases for fleet.fuel.expense model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for fuel expense tests."""
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.currency = cls.company.currency_id

        # Create vehicle brand and model
        cls.vehicle_brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Expense Test Brand',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Expense Test Model',
            'brand_id': cls.vehicle_brand.id,
        })

        # Create test vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'EXPENSE-001',
            'company_id': cls.company.id,
        })

        # Create second vehicle for constraint tests
        cls.vehicle_2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'EXPENSE-002',
            'company_id': cls.company.id,
        })

        # Create test driver
        cls.driver = cls.env['hr.employee'].create({
            'name': 'Expense Test Driver',
            'company_id': cls.company.id,
        })

        # Create test fuel card with sufficient balance
        cls.card = cls.env['fleet.fuel.card'].create({
            'card_uid': 'EXPENSE-CARD-001',
            'vehicle_id': cls.vehicle.id,
            'driver_id': cls.driver.id,
            'balance_amount': 5000.0,
            'pending_amount': 0.0,
            'company_id': cls.company.id,
        })
        cls.card.action_activate()

        # Create a card with low balance for insufficient balance tests
        cls.card_low_balance = cls.env['fleet.fuel.card'].create({
            'card_uid': 'EXPENSE-CARD-LOW',
            'vehicle_id': cls.vehicle.id,
            'balance_amount': 50.0,
            'pending_amount': 0.0,
            'company_id': cls.company.id,
        })
        cls.card_low_balance.action_activate()

        # Create a test station partner
        cls.station = cls.env['res.partner'].create({
            'name': 'Test Fuel Station',
            'supplier_rank': 1,
        })

        # Dummy receipt attachment (required field)
        cls.dummy_receipt = base64.b64encode(b'Test receipt content for expense validation')

        cls.Expense = cls.env['fleet.fuel.expense']
        cls.BalanceService = cls.env['fleet.fuel.balance.service']

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _create_expense(self, card=None, vehicle=None, amount=100.0, **kwargs):
        """Helper to create expense with required fields."""
        vals = {
            'card_id': (card or self.card).id,
            'vehicle_id': (vehicle or self.vehicle).id,
            'amount': amount,
            'expense_date': fields.Date.today(),
            'receipt_attachment': self.dummy_receipt,
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.Expense.create(vals)

    # -------------------------------------------------------------------------
    # TEST: BASIC CRUD OPERATIONS
    # -------------------------------------------------------------------------
    def test_01_expense_creation_basic(self):
        """Test basic expense creation with auto-generated sequence."""
        expense = self._create_expense(amount=150.0)

        self.assertTrue(expense.exists())
        self.assertEqual(expense.state, 'draft')
        self.assertTrue(expense.name, "Expense name should be auto-generated")
        self.assertEqual(expense.amount, 150.0)
        self.assertEqual(expense.card_id, self.card)
        self.assertEqual(expense.vehicle_id, self.vehicle)
        self.assertEqual(expense.company_id, self.company)
        self.assertEqual(expense.currency_id, self.currency)

    def test_02_expense_creation_with_liters(self):
        """Test expense creation with liter quantity."""
        expense = self._create_expense(amount=200.0, liter_qty=50.0)

        self.assertEqual(expense.amount, 200.0)
        self.assertEqual(expense.liter_qty, 50.0)

    def test_03_expense_creation_with_odometer(self):
        """Test expense creation with odometer reading."""
        expense = self._create_expense(amount=100.0, odometer=15000.0)

        self.assertEqual(expense.odometer, 15000.0)

    def test_04_expense_creation_with_station(self):
        """Test expense creation with station partner."""
        expense = self._create_expense(
            amount=120.0,
            station_partner_id=self.station.id,
        )

        self.assertEqual(expense.station_partner_id, self.station)

    def test_05_expense_auto_fill_from_card(self):
        """Test that vehicle/driver are auto-filled from card."""
        expense = self.Expense.create({
            'card_id': self.card.id,
            'amount': 100.0,
            'expense_date': fields.Date.today(),
            'receipt_attachment': self.dummy_receipt,
        })

        self.assertEqual(expense.vehicle_id, self.card.vehicle_id)
        self.assertEqual(expense.driver_id, self.card.driver_id)

    # -------------------------------------------------------------------------
    # TEST: AMOUNT VALIDATION (SQL CONSTRAINT)
    # -------------------------------------------------------------------------
    def test_06_expense_amount_positive_constraint(self):
        """Test that amount must be positive (SQL constraint)."""
        with self.assertRaises(Exception):
            self._create_expense(amount=0.0)

    def test_07_expense_amount_negative_constraint(self):
        """Test that negative amount raises error."""
        with self.assertRaises(Exception):
            self._create_expense(amount=-50.0)

    # -------------------------------------------------------------------------
    # TEST: LITER QUANTITY CONSTRAINT
    # -------------------------------------------------------------------------
    def test_08_expense_liter_zero_valid(self):
        """Test that zero liters is valid."""
        expense = self._create_expense(amount=100.0, liter_qty=0.0)
        self.assertEqual(expense.liter_qty, 0.0)

    def test_09_expense_liter_negative_constraint(self):
        """Test that negative liters raises error (SQL constraint)."""
        with self.assertRaises(Exception):
            self._create_expense(amount=100.0, liter_qty=-10.0)

    # -------------------------------------------------------------------------
    # TEST: RECEIPT ATTACHMENT CONSTRAINT
    # -------------------------------------------------------------------------
    def test_10_expense_receipt_required(self):
        """Test that receipt attachment is required."""
        with self.assertRaises(ValidationError):
            self.Expense.create({
                'card_id': self.card.id,
                'vehicle_id': self.vehicle.id,
                'amount': 100.0,
                'expense_date': fields.Date.today(),
                # Missing receipt_attachment
                'company_id': self.company.id,
            })

    # -------------------------------------------------------------------------
    # TEST: PRICE PER LITER COMPUTATION
    # -------------------------------------------------------------------------
    def test_11_price_per_liter_computation(self):
        """Test price_per_liter computed field."""
        expense = self._create_expense(amount=200.0, liter_qty=50.0)

        self.assertEqual(expense.price_per_liter, 4.0)  # 200 / 50 = 4

    def test_12_price_per_liter_zero_liters(self):
        """Test price_per_liter when liters is zero."""
        expense = self._create_expense(amount=100.0, liter_qty=0.0)

        self.assertEqual(expense.price_per_liter, 0.0)

    def test_13_price_per_liter_update(self):
        """Test price_per_liter updates on change."""
        expense = self._create_expense(amount=150.0, liter_qty=30.0)
        self.assertEqual(expense.price_per_liter, 5.0)

        expense.write({'liter_qty': 50.0})
        expense.invalidate_recordset(['price_per_liter'])
        self.assertEqual(expense.price_per_liter, 3.0)  # 150 / 50 = 3

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - SUBMIT
    # -------------------------------------------------------------------------
    def test_14_expense_submit_workflow(self):
        """Test expense submission workflow."""
        expense = self._create_expense(amount=100.0)
        self.assertEqual(expense.state, 'draft')

        expense.action_submit()

        self.assertEqual(expense.state, 'submitted')
        self.assertEqual(expense.submitted_by_id, self.env.user)

    def test_15_expense_submit_idempotent(self):
        """Test submitting already submitted expense does nothing."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()
        self.assertEqual(expense.state, 'submitted')

        # Submit again
        expense.action_submit()
        self.assertEqual(expense.state, 'submitted')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - VALIDATE (BALANCE DEDUCTION)
    # -------------------------------------------------------------------------
    def test_16_expense_validate_workflow(self):
        """Test expense validation workflow."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()

        expense.action_validate()

        self.assertEqual(expense.state, 'validated')
        self.assertTrue(expense.validated_by_id)
        self.assertTrue(expense.validated_date)

    def test_17_expense_validate_deducts_balance(self):
        """Test that validation deducts from card balance."""
        # Create a card with known balance
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'VALIDATE-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        expense = self._create_expense(card=test_card, amount=250.0)
        expense.action_submit()
        expense.action_validate()

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 750.0)  # 1000 - 250

    def test_18_expense_validate_from_draft(self):
        """Test validating directly from draft state."""
        expense = self._create_expense(amount=50.0)

        expense.action_validate()

        self.assertEqual(expense.state, 'validated')

    def test_19_expense_insufficient_balance_blocked(self):
        """Test that expense is blocked when insufficient balance."""
        expense = self._create_expense(
            card=self.card_low_balance,
            amount=100.0,  # More than 50.0 available
        )

        with self.assertRaises(ValidationError):
            expense.action_validate()

    def test_20_expense_validate_multiple_deductions(self):
        """Test multiple expense validations deduct correctly."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'MULTI-DEDUCT-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 500.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        # First expense
        expense1 = self._create_expense(card=test_card, amount=100.0)
        expense1.action_validate()

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 400.0)

        # Second expense
        expense2 = self._create_expense(card=test_card, amount=150.0)
        expense2.action_validate()

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 250.0)

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - REJECT
    # -------------------------------------------------------------------------
    def test_21_expense_reject_workflow(self):
        """Test expense rejection workflow."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()

        expense.action_reject()

        self.assertEqual(expense.state, 'rejected')

    def test_22_expense_reject_from_draft(self):
        """Test rejecting directly from draft state."""
        expense = self._create_expense(amount=100.0)

        expense.action_reject()

        self.assertEqual(expense.state, 'rejected')

    def test_23_expense_reject_validated_fails(self):
        """Test that rejecting a validated expense fails."""
        expense = self._create_expense(amount=50.0)
        expense.action_validate()

        with self.assertRaises(UserError):
            expense.action_reject()

    def test_24_expense_reject_with_reason(self):
        """Test rejection with reason message."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()

        expense.action_reject(reason="Missing proper documentation")

        self.assertEqual(expense.state, 'rejected')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - RESET TO DRAFT
    # -------------------------------------------------------------------------
    def test_25_expense_reset_to_draft(self):
        """Test resetting rejected expense to draft."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()
        expense.action_reject()
        self.assertEqual(expense.state, 'rejected')

        expense.action_reset_to_draft()

        self.assertEqual(expense.state, 'draft')

    def test_26_expense_reset_non_rejected_fails(self):
        """Test that resetting non-rejected expense fails."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()

        with self.assertRaises(UserError):
            expense.action_reset_to_draft()

    # -------------------------------------------------------------------------
    # TEST: ODOMETER VALIDATION
    # -------------------------------------------------------------------------
    def test_27_expense_odometer_positive(self):
        """Test valid positive odometer value."""
        expense = self._create_expense(amount=100.0, odometer=50000.0)
        self.assertEqual(expense.odometer, 50000.0)

    def test_28_expense_odometer_zero_valid(self):
        """Test that zero odometer is valid (not set)."""
        expense = self._create_expense(amount=100.0, odometer=0.0)
        self.assertEqual(expense.odometer, 0.0)

    def test_29_expense_odometer_negative_constraint(self):
        """Test that negative odometer raises error."""
        with self.assertRaises(ValidationError):
            self._create_expense(amount=100.0, odometer=-1000.0)

    # -------------------------------------------------------------------------
    # TEST: CARD/VEHICLE CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_30_expense_card_vehicle_mismatch(self):
        """Test that card and vehicle must match."""
        # Card is linked to self.vehicle, trying to use self.vehicle_2
        with self.assertRaises(ValidationError):
            self._create_expense(
                card=self.card,
                vehicle=self.vehicle_2,  # Different from card's vehicle
                amount=100.0,
            )

    # -------------------------------------------------------------------------
    # TEST: DELETE RESTRICTIONS
    # -------------------------------------------------------------------------
    def test_31_expense_delete_draft(self):
        """Test deleting draft expense is allowed."""
        expense = self._create_expense(amount=100.0)

        expense.unlink()

        self.assertFalse(expense.exists())

    def test_32_expense_delete_rejected(self):
        """Test deleting rejected expense is allowed."""
        expense = self._create_expense(amount=100.0)
        expense.action_reject()

        expense.unlink()

        self.assertFalse(expense.exists())

    def test_33_expense_delete_submitted_fails(self):
        """Test deleting submitted expense fails."""
        expense = self._create_expense(amount=100.0)
        expense.action_submit()

        with self.assertRaises(UserError):
            expense.unlink()

    def test_34_expense_delete_validated_fails(self):
        """Test deleting validated expense fails."""
        expense = self._create_expense(amount=50.0)
        expense.action_validate()

        with self.assertRaises(UserError):
            expense.unlink()

    # -------------------------------------------------------------------------
    # TEST: WRITE RESTRICTIONS
    # -------------------------------------------------------------------------
    def test_35_expense_write_validated_card_fails(self):
        """Test that changing card on validated expense fails."""
        expense = self._create_expense(amount=50.0)
        expense.action_validate()

        # Create another card
        other_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'OTHER-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'company_id': self.company.id,
        })
        other_card.action_activate()

        with self.assertRaises(UserError):
            expense.write({'card_id': other_card.id})

    # -------------------------------------------------------------------------
    # TEST: IMPORT HASH
    # -------------------------------------------------------------------------
    def test_36_expense_import_hash_generation(self):
        """Test that import_hash is auto-generated."""
        expense = self._create_expense(
            amount=123.45,
            liter_qty=25.5,
        )

        self.assertTrue(expense.import_hash)

    def test_37_expense_import_hash_unique(self):
        """Test that duplicate import_hash raises error."""
        expense1 = self._create_expense(
            amount=100.0,
            liter_qty=25.0,
        )

        # Creating identical expense should fail due to unique hash
        with self.assertRaises(Exception):
            self._create_expense(
                amount=100.0,
                liter_qty=25.0,
            )

    # -------------------------------------------------------------------------
    # TEST: BATCH CREATION
    # -------------------------------------------------------------------------
    def test_38_expense_batch_creation(self):
        """Test creating multiple expenses at once."""
        expenses_vals = [
            {
                'card_id': self.card.id,
                'vehicle_id': self.vehicle.id,
                'amount': 100.0,
                'expense_date': fields.Date.today(),
                'receipt_attachment': self.dummy_receipt,
                'company_id': self.company.id,
                'liter_qty': 20.0,
            },
            {
                'card_id': self.card.id,
                'vehicle_id': self.vehicle.id,
                'amount': 200.0,
                'expense_date': fields.Date.today(),
                'receipt_attachment': self.dummy_receipt,
                'company_id': self.company.id,
                'liter_qty': 40.0,
            },
        ]

        expenses = self.Expense.create(expenses_vals)

        self.assertEqual(len(expenses), 2)
        self.assertTrue(all(e.name for e in expenses))
        self.assertEqual(expenses[0].amount, 100.0)
        self.assertEqual(expenses[1].amount, 200.0)

    # -------------------------------------------------------------------------
    # TEST: BALANCE SERVICE SPEND METHOD
    # -------------------------------------------------------------------------
    def test_39_balance_service_spend_amount(self):
        """Test balance service spend_amount method."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SPEND-CARD-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 500.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.spend_amount(test_card, 200.0)

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 300.0)

    def test_40_balance_service_spend_insufficient(self):
        """Test spend_amount with insufficient balance."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SPEND-CARD-002',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 50.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        with self.assertRaises(ValidationError):
            self.BalanceService.spend_amount(test_card, 100.0)

    def test_41_balance_service_spend_zero(self):
        """Test spend_amount with zero amount does nothing."""
        test_card = self.env['fleet.fuel.card'].create({
            'card_uid': 'SPEND-CARD-003',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 100.0,
            'company_id': self.company.id,
        })
        test_card.action_activate()

        self.BalanceService.spend_amount(test_card, 0.0)

        test_card.invalidate_recordset(['balance_amount'])
        self.assertEqual(test_card.balance_amount, 100.0)  # Unchanged
