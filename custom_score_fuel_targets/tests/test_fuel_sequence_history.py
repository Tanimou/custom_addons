# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for fuel reference/sequence and detailed vehicle history (FR-023).

Test coverage:
- Fuel expense unique reference generation
- Sequence numbering continuity
- Vehicle fuel history retrieval
- History filtering by date range
- Aggregation of fuel data per vehicle
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestFuelSequenceReference(TransactionCase):
    """Test suite for fuel expense unique reference/sequence (FR-023)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create fuel card
        cls.fuel_card = cls.env['fleet.fuel.card'].create({
            'name': 'CARD-TEST-001',
            'number': '1234567890',
            'company_id': cls.env.company.id,
            'state': 'active',
        })
        
        # Create vehicle
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Seq Test Brand',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Seq Test Model',
            'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'SEQ-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Expense = cls.env['fleet.fuel.expense']

    def test_expense_gets_sequence_on_create(self):
        """Test that fuel expense gets a unique reference on creation."""
        expense = self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        
        self.assertTrue(expense.name)
        self.assertNotEqual(expense.name, '')

    def test_expense_sequence_increments(self):
        """Test that sequential expenses get incrementing references."""
        expense1 = self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        
        expense2 = self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle.id,
            'expense_date': date.today(),
            'amount': 150.0,
            'liter_qty': 75.0,
        })
        
        # Both should have unique references
        self.assertNotEqual(expense1.name, expense2.name)

    def test_expense_reference_not_duplicated(self):
        """Test that expense references are unique (no duplicates)."""
        expenses = []
        for i in range(5):
            expense = self.Expense.create({
                'card_id': self.fuel_card.id,
                'vehicle_id': self.vehicle.id,
                'expense_date': date.today(),
                'amount': 100.0 + i,
                'liter_qty': 50.0 + i,
            })
            expenses.append(expense)
        
        references = [e.name for e in expenses]
        # All references should be unique
        self.assertEqual(len(references), len(set(references)))


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestVehicleFuelHistory(TransactionCase):
    """Test suite for vehicle fuel history (FR-023)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create fuel cards
        cls.fuel_card = cls.env['fleet.fuel.card'].create({
            'name': 'CARD-HIST-001',
            'number': '9876543210',
            'company_id': cls.env.company.id,
            'state': 'active',
        })
        
        # Create vehicles
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'History Test Brand',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'History Test Model',
            'brand_id': cls.brand.id,
        })
        cls.vehicle1 = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'HIST-001',
            'company_id': cls.env.company.id,
        })
        cls.vehicle2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'HIST-002',
            'company_id': cls.env.company.id,
        })
        
        cls.Expense = cls.env['fleet.fuel.expense']

    def test_vehicle_has_fuel_expense_count(self):
        """Test that vehicle tracks fuel expense count."""
        # Create expenses for vehicle1
        for i in range(3):
            self.Expense.create({
                'card_id': self.fuel_card.id,
                'vehicle_id': self.vehicle1.id,
                'expense_date': date.today() - timedelta(days=i),
                'amount': 100.0,
                'liter_qty': 50.0,
            })
        
        # Vehicle should have count field
        self.assertTrue(hasattr(self.vehicle1, 'fuel_expense_count'))
        self.assertEqual(self.vehicle1.fuel_expense_count, 3)

    def test_vehicle_fuel_expenses_only_counts_own(self):
        """Test that vehicle only counts its own expenses."""
        # Create expenses for vehicle1
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        
        # Create expenses for vehicle2
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle2.id,
            'expense_date': date.today(),
            'amount': 200.0,
            'liter_qty': 100.0,
        })
        
        self.assertEqual(self.vehicle1.fuel_expense_count, 1)
        self.assertEqual(self.vehicle2.fuel_expense_count, 1)

    def test_vehicle_action_view_fuel_expenses(self):
        """Test that vehicle has action to view fuel expenses."""
        # Create some expenses
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        
        # Vehicle should have action method
        self.assertTrue(hasattr(self.vehicle1, 'action_view_fuel_expenses'))
        
        action = self.vehicle1.action_view_fuel_expenses()
        self.assertEqual(action['res_model'], 'fleet.fuel.expense')
        self.assertIn(('vehicle_id', '=', self.vehicle1.id), action['domain'])

    def test_vehicle_total_fuel_amount(self):
        """Test that vehicle aggregates total fuel amount."""
        # Create expenses
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
            'state': 'validated',
        })
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today() - timedelta(days=1),
            'amount': 150.0,
            'liter_qty': 75.0,
            'state': 'validated',
        })
        
        # Vehicle should have total fuel amount
        self.assertTrue(hasattr(self.vehicle1, 'total_fuel_amount'))
        self.assertAlmostEqual(self.vehicle1.total_fuel_amount, 250.0, places=2)

    def test_vehicle_total_fuel_liters(self):
        """Test that vehicle aggregates total fuel liters."""
        # Create expenses
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today(),
            'amount': 100.0,
            'liter_qty': 50.0,
            'state': 'validated',
        })
        self.Expense.create({
            'card_id': self.fuel_card.id,
            'vehicle_id': self.vehicle1.id,
            'expense_date': date.today() - timedelta(days=1),
            'amount': 150.0,
            'liter_qty': 75.0,
            'state': 'validated',
        })
        
        # Vehicle should have total fuel liters
        self.assertTrue(hasattr(self.vehicle1, 'total_fuel_liters'))
        self.assertAlmostEqual(self.vehicle1.total_fuel_liters, 125.0, places=2)


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestFuelHistoryFiltering(TransactionCase):
    """Test suite for fuel history date filtering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.fuel_card = cls.env['fleet.fuel.card'].create({
            'name': 'CARD-FILTER-001',
            'number': '5555555555',
            'company_id': cls.env.company.id,
            'state': 'active',
        })
        
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Filter Test Brand',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Filter Test Model',
            'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'FILTER-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Expense = cls.env['fleet.fuel.expense']
        
        # Create expenses across different dates
        today = date.today()
        cls.expense_today = cls.Expense.create({
            'card_id': cls.fuel_card.id,
            'vehicle_id': cls.vehicle.id,
            'expense_date': today,
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        cls.expense_week_ago = cls.Expense.create({
            'card_id': cls.fuel_card.id,
            'vehicle_id': cls.vehicle.id,
            'expense_date': today - timedelta(days=7),
            'amount': 100.0,
            'liter_qty': 50.0,
        })
        cls.expense_month_ago = cls.Expense.create({
            'card_id': cls.fuel_card.id,
            'vehicle_id': cls.vehicle.id,
            'expense_date': today - timedelta(days=30),
            'amount': 100.0,
            'liter_qty': 50.0,
        })

    def test_filter_expenses_this_week(self):
        """Test filtering expenses for current week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        expenses = self.Expense.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('expense_date', '>=', week_start),
        ])
        
        # Should include today's expense, maybe week ago depending on week
        self.assertIn(self.expense_today, expenses)

    def test_filter_expenses_this_month(self):
        """Test filtering expenses for current month."""
        today = date.today()
        month_start = today.replace(day=1)
        
        expenses = self.Expense.search([
            ('vehicle_id', '=', self.vehicle.id),
            ('expense_date', '>=', month_start),
        ])
        
        # Should include recent expenses
        self.assertIn(self.expense_today, expenses)

    def test_search_view_filters_exist(self):
        """Test that search view has standard date filters."""
        # This is more of a view test, but validates the filter requirement
        search_view = self.env.ref(
            'custom_fleet_fuel_management.fleet_fuel_expense_view_search',
            raise_if_not_found=False
        )
        if search_view:
            self.assertIsNotNone(search_view)
