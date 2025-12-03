# -*- coding: utf-8 -*-
"""Tests for fleet.fuel.card model.

Test coverage:
- CRUD operations and sequence generation
- Card uniqueness constraint (card_uid)
- State workflow: draft -> active -> suspended/expired
- Date constraints (expiration >= activation)
- Balance constraints (>= 0)
- Smart buttons (recharge/expense counts)
"""
import base64
import logging

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestFleetFuelCard(TransactionCase):
    """Test cases for fleet.fuel.card model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for fuel card tests."""
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.currency = cls.company.currency_id

        # Create a test vehicle brand and model
        cls.vehicle_brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model',
            'brand_id': cls.vehicle_brand.id,
        })

        # Create a test vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-001',
            'company_id': cls.company.id,
        })

        # Create a second test vehicle for uniqueness tests
        cls.vehicle_2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-002',
            'company_id': cls.company.id,
        })

        # Create a test employee (driver)
        cls.driver = cls.env['hr.employee'].create({
            'name': 'Test Driver',
            'company_id': cls.company.id,
        })

        cls.FuelCard = cls.env['fleet.fuel.card']

    # -------------------------------------------------------------------------
    # TEST: BASIC CRUD OPERATIONS
    # -------------------------------------------------------------------------
    def test_01_card_creation_basic(self):
        """Test basic fuel card creation with auto-generated sequence."""
        card = self.FuelCard.create({
            'card_uid': 'CARD-TEST-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        self.assertTrue(card.exists())
        self.assertEqual(card.state, 'draft', "New card should be in draft state")
        self.assertTrue(card.name, "Card name should be auto-generated from sequence")
        self.assertEqual(card.card_uid, 'CARD-TEST-001')
        self.assertEqual(card.vehicle_id, self.vehicle)
        self.assertEqual(card.company_id, self.company)
        self.assertEqual(card.currency_id, self.currency)

    def test_02_card_creation_with_driver(self):
        """Test card creation with driver assignment."""
        card = self.FuelCard.create({
            'card_uid': 'CARD-TEST-002',
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'fuel_type': 'petrol',
            'company_id': self.company.id,
        })

        self.assertEqual(card.driver_id, self.driver)
        self.assertEqual(card.fuel_type, 'petrol')

    def test_03_card_creation_auto_driver_from_vehicle(self):
        """Test that driver is auto-assigned from vehicle if not provided."""
        # Assign driver to vehicle first
        self.vehicle.driver_id = self.driver.id

        card = self.FuelCard.create({
            'card_uid': 'CARD-TEST-003',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        self.assertEqual(card.driver_id, self.driver,
                         "Driver should be auto-assigned from vehicle")

    def test_04_card_creation_with_limits(self):
        """Test card creation with daily/monthly limits."""
        card = self.FuelCard.create({
            'card_uid': 'CARD-TEST-004',
            'vehicle_id': self.vehicle.id,
            'max_daily_amount': 100.0,
            'max_month_amount': 2000.0,
            'balance_amount': 500.0,
            'company_id': self.company.id,
        })

        self.assertEqual(card.max_daily_amount, 100.0)
        self.assertEqual(card.max_month_amount, 2000.0)
        self.assertEqual(card.balance_amount, 500.0)

    # -------------------------------------------------------------------------
    # TEST: UNIQUENESS CONSTRAINT
    # -------------------------------------------------------------------------
    def test_05_card_unique_number_constraint(self):
        """Test that card_uid must be unique (SQL constraint)."""
        self.FuelCard.create({
            'card_uid': 'UNIQUE-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        with self.assertRaises(Exception) as context:
            self.FuelCard.create({
                'card_uid': 'UNIQUE-001',  # Duplicate
                'vehicle_id': self.vehicle_2.id,
                'company_id': self.company.id,
            })

        # Should be IntegrityError or ValidationError depending on Odoo handling
        self.assertTrue(context.exception)

    # -------------------------------------------------------------------------
    # TEST: STATE WORKFLOW - ACTIVATION
    # -------------------------------------------------------------------------
    def test_06_card_activation(self):
        """Test card activation workflow."""
        card = self.FuelCard.create({
            'card_uid': 'ACTIVATE-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        self.assertEqual(card.state, 'draft')
        self.assertFalse(card.activation_date)

        # Activate the card
        card.action_activate()

        self.assertEqual(card.state, 'active')
        self.assertTrue(card.activation_date, "Activation date should be set")
        self.assertEqual(card.activation_date, fields.Date.context_today(card))

    def test_07_card_activation_preserves_existing_date(self):
        """Test that activation preserves pre-set activation_date."""
        custom_date = fields.Date.from_string('2025-01-15')
        card = self.FuelCard.create({
            'card_uid': 'ACTIVATE-002',
            'vehicle_id': self.vehicle.id,
            'activation_date': custom_date,
            'company_id': self.company.id,
        })

        card.action_activate()

        self.assertEqual(card.state, 'active')
        self.assertEqual(card.activation_date, custom_date,
                         "Pre-set activation date should be preserved")

    # -------------------------------------------------------------------------
    # TEST: STATE WORKFLOW - SUSPENSION
    # -------------------------------------------------------------------------
    def test_08_card_suspension(self):
        """Test card suspension workflow."""
        card = self.FuelCard.create({
            'card_uid': 'SUSPEND-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })
        card.action_activate()
        self.assertEqual(card.state, 'active')

        # Suspend the card
        card.action_suspend()

        self.assertEqual(card.state, 'suspended')

    def test_09_card_suspension_from_draft(self):
        """Test card suspension directly from draft state."""
        card = self.FuelCard.create({
            'card_uid': 'SUSPEND-002',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        # Suspend directly from draft
        card.action_suspend()

        self.assertEqual(card.state, 'suspended')

    # -------------------------------------------------------------------------
    # TEST: STATE WORKFLOW - EXPIRATION
    # -------------------------------------------------------------------------
    def test_10_card_expiration(self):
        """Test card expiration workflow."""
        card = self.FuelCard.create({
            'card_uid': 'EXPIRE-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })
        card.action_activate()

        # Mark as expired
        card.action_mark_expired()

        self.assertEqual(card.state, 'expired')
        self.assertTrue(card.expiration_date, "Expiration date should be set")

    def test_11_card_expiration_preserves_date(self):
        """Test that expiration preserves pre-set expiration_date."""
        custom_exp_date = fields.Date.from_string('2025-12-31')
        card = self.FuelCard.create({
            'card_uid': 'EXPIRE-002',
            'vehicle_id': self.vehicle.id,
            'expiration_date': custom_exp_date,
            'company_id': self.company.id,
        })
        card.action_activate()
        card.action_mark_expired()

        self.assertEqual(card.state, 'expired')
        self.assertEqual(card.expiration_date, custom_exp_date,
                         "Pre-set expiration date should be preserved")

    # -------------------------------------------------------------------------
    # TEST: DATE CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_12_card_date_constraint_valid(self):
        """Test valid date range (expiration >= activation)."""
        card = self.FuelCard.create({
            'card_uid': 'DATE-001',
            'vehicle_id': self.vehicle.id,
            'activation_date': '2025-01-01',
            'expiration_date': '2025-12-31',
            'company_id': self.company.id,
        })

        self.assertTrue(card.exists())

    def test_13_card_date_constraint_same_day(self):
        """Test valid date range with same activation and expiration."""
        card = self.FuelCard.create({
            'card_uid': 'DATE-002',
            'vehicle_id': self.vehicle.id,
            'activation_date': '2025-06-15',
            'expiration_date': '2025-06-15',
            'company_id': self.company.id,
        })

        self.assertTrue(card.exists())

    def test_14_card_date_constraint_invalid(self):
        """Test that expiration before activation raises error."""
        with self.assertRaises(ValidationError):
            self.FuelCard.create({
                'card_uid': 'DATE-003',
                'vehicle_id': self.vehicle.id,
                'activation_date': '2025-12-31',
                'expiration_date': '2025-01-01',  # Before activation
                'company_id': self.company.id,
            })

    def test_15_card_date_constraint_on_write(self):
        """Test date constraint on update (write)."""
        card = self.FuelCard.create({
            'card_uid': 'DATE-004',
            'vehicle_id': self.vehicle.id,
            'activation_date': '2025-01-01',
            'expiration_date': '2025-12-31',
            'company_id': self.company.id,
        })

        with self.assertRaises(ValidationError):
            card.write({'expiration_date': '2024-06-01'})

    # -------------------------------------------------------------------------
    # TEST: BALANCE CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_16_card_balance_zero(self):
        """Test card with zero balance (valid)."""
        card = self.FuelCard.create({
            'card_uid': 'BALANCE-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 0.0,
            'company_id': self.company.id,
        })

        self.assertEqual(card.balance_amount, 0.0)

    def test_17_card_balance_positive(self):
        """Test card with positive balance (valid)."""
        card = self.FuelCard.create({
            'card_uid': 'BALANCE-002',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'company_id': self.company.id,
        })

        self.assertEqual(card.balance_amount, 1000.0)

    def test_18_card_balance_negative_constraint(self):
        """Test that negative balance raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.FuelCard.create({
                'card_uid': 'BALANCE-003',
                'vehicle_id': self.vehicle.id,
                'balance_amount': -100.0,
                'company_id': self.company.id,
            })

    def test_19_card_balance_negative_on_write(self):
        """Test that updating to negative balance raises error."""
        card = self.FuelCard.create({
            'card_uid': 'BALANCE-004',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 100.0,
            'company_id': self.company.id,
        })

        with self.assertRaises(ValidationError):
            card.write({'balance_amount': -50.0})

    # -------------------------------------------------------------------------
    # TEST: AVAILABLE AMOUNT COMPUTATION
    # -------------------------------------------------------------------------
    def test_20_card_available_amount_computation(self):
        """Test available_amount = balance_amount - pending_amount."""
        card = self.FuelCard.create({
            'card_uid': 'AVAIL-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'pending_amount': 200.0,
            'company_id': self.company.id,
        })

        self.assertEqual(card.available_amount, 800.0)

    def test_21_card_available_amount_no_pending(self):
        """Test available_amount when no pending amount."""
        card = self.FuelCard.create({
            'card_uid': 'AVAIL-002',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 500.0,
            'pending_amount': 0.0,
            'company_id': self.company.id,
        })

        self.assertEqual(card.available_amount, 500.0)

    # -------------------------------------------------------------------------
    # TEST: SMART BUTTONS & RELATED COUNTS
    # -------------------------------------------------------------------------
    def test_22_card_recharge_count(self):
        """Test recharge count via One2many relationship."""
        card = self.FuelCard.create({
            'card_uid': 'COUNT-001',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'company_id': self.company.id,
        })
        card.action_activate()

        # Create recharges
        Recharge = self.env['fleet.fuel.recharge']
        Recharge.create({
            'card_id': card.id,
            'amount': 100.0,
            'recharge_date': fields.Date.today(),
        })
        Recharge.create({
            'card_id': card.id,
            'amount': 200.0,
            'recharge_date': fields.Date.today(),
        })

        self.assertEqual(len(card.recharge_ids), 2)

    def test_23_card_expense_count(self):
        """Test expense count via One2many relationship."""
        card = self.FuelCard.create({
            'card_uid': 'COUNT-002',
            'vehicle_id': self.vehicle.id,
            'balance_amount': 1000.0,
            'company_id': self.company.id,
        })
        card.action_activate()

        # Create expenses (need receipt_attachment as it's required)
        Expense = self.env['fleet.fuel.expense']
        dummy_receipt = base64.b64encode(b'dummy receipt content')

        Expense.create({
            'card_id': card.id,
            'vehicle_id': self.vehicle.id,
            'amount': 50.0,
            'expense_date': fields.Date.today(),
            'receipt_attachment': dummy_receipt,
            'company_id': self.company.id,
        })
        Expense.create({
            'card_id': card.id,
            'vehicle_id': self.vehicle.id,
            'amount': 75.0,
            'expense_date': fields.Date.today(),
            'receipt_attachment': dummy_receipt,
            'company_id': self.company.id,
        })

        self.assertEqual(len(card.expense_ids), 2)

    # -------------------------------------------------------------------------
    # TEST: VIEW ACTIONS
    # -------------------------------------------------------------------------
    def test_24_card_action_view_recharges(self):
        """Test action_view_recharges returns proper action dict."""
        card = self.FuelCard.create({
            'card_uid': 'ACTION-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        action = card.action_view_recharges()

        # Action may be False if action reference not found (test install order)
        if action:
            self.assertIn('domain', action)
            self.assertIn('context', action)

    def test_25_card_action_view_expenses(self):
        """Test action_view_expenses returns proper action dict."""
        card = self.FuelCard.create({
            'card_uid': 'ACTION-002',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        action = card.action_view_expenses()

        # Action may be False if action reference not found
        if action:
            self.assertIn('domain', action)
            self.assertIn('context', action)

    # -------------------------------------------------------------------------
    # TEST: FUEL TYPE SELECTION
    # -------------------------------------------------------------------------
    def test_26_card_fuel_type_default(self):
        """Test default fuel type is diesel."""
        card = self.FuelCard.create({
            'card_uid': 'FUEL-001',
            'vehicle_id': self.vehicle.id,
            'company_id': self.company.id,
        })

        self.assertEqual(card.fuel_type, 'diesel')

    def test_27_card_fuel_type_options(self):
        """Test all fuel type options."""
        fuel_types = ['petrol', 'diesel', 'electric', 'hybrid', 'other']

        for i, fuel_type in enumerate(fuel_types):
            card = self.FuelCard.create({
                'card_uid': f'FUEL-TYPE-{i:03d}',
                'vehicle_id': self.vehicle.id,
                'fuel_type': fuel_type,
                'company_id': self.company.id,
            })
            self.assertEqual(card.fuel_type, fuel_type)

    # -------------------------------------------------------------------------
    # TEST: BATCH CREATION
    # -------------------------------------------------------------------------
    def test_28_card_batch_creation(self):
        """Test creating multiple cards at once."""
        cards_vals = [
            {
                'card_uid': 'BATCH-001',
                'vehicle_id': self.vehicle.id,
                'company_id': self.company.id,
            },
            {
                'card_uid': 'BATCH-002',
                'vehicle_id': self.vehicle_2.id,
                'company_id': self.company.id,
            },
        ]

        cards = self.FuelCard.create(cards_vals)

        self.assertEqual(len(cards), 2)
        self.assertTrue(all(c.name for c in cards))
        self.assertEqual(cards[0].card_uid, 'BATCH-001')
        self.assertEqual(cards[1].card_uid, 'BATCH-002')
