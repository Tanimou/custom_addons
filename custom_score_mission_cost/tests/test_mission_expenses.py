# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for mission expenses, cost consolidation, and cost/km KPI.
FR-014: Mission expense consolidation (toll, fuel, maintenance, other)
FR-015: Cost per kilometer calculation
FR-026: Analytic propagation
"""

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestMissionExpenses(TransactionCase):
    """Test suite for mission expense totals, analytic propagation, and cost/km KPI."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Create a partner (driver)
        cls.driver = cls.env['res.partner'].create({
            'name': 'Test Driver Expense',
            'email': 'driver.expense@test.score',
        })
        
        # Create a vehicle
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Expense',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Expense',
            'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'name': 'Test Vehicle Expense',
            'model_id': cls.model.id,
            'license_plate': 'TEST-EXP-01',
        })
        
        # Create analytic plan and account (if analytic module is installed)
        cls.analytic_account = None
        if 'account.analytic.account' in cls.env:
            # Find or create an analytic plan
            plan = cls.env['account.analytic.plan'].search([], limit=1)
            if not plan:
                plan = cls.env['account.analytic.plan'].create({
                    'name': 'Test Plan SCORE',
                })
            cls.analytic_account = cls.env['account.analytic.account'].create({
                'name': 'Test Analytic Account',
                'plan_id': plan.id,
            })

    def _create_mission(self, **kwargs):
        """Helper to create a mission with default values."""
        vals = {
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'destination': 'Test Destination',
            'objective': 'Test Objective',
            'mission_type': 'intercity',
        }
        vals.update(kwargs)
        return self.env['fleet.mission'].create(vals)

    def _create_expense(self, mission, expense_type='toll', amount=100.0, **kwargs):
        """Helper to create a mission expense."""
        vals = {
            'mission_id': mission.id,
            'expense_type': expense_type,
            'amount': amount,
            'date': datetime.now().date(),
            'description': f'Test {expense_type} expense',
        }
        vals.update(kwargs)
        return self.env['fleet.mission.expense'].create(vals)

    # ========== FR-014: Expense Creation and Consolidation ==========

    def test_expense_creation_basic(self):
        """Can create a basic expense linked to a mission."""
        mission = self._create_mission()
        expense = self._create_expense(mission, 'toll', 50.0)
        
        self.assertEqual(expense.mission_id, mission)
        self.assertEqual(expense.expense_type, 'toll')
        self.assertEqual(expense.amount, 50.0)

    def test_expense_types_available(self):
        """All expense types should be available: toll, fuel, maintenance, parking, other."""
        mission = self._create_mission()
        
        for etype in ['toll', 'fuel', 'maintenance', 'parking', 'other']:
            expense = self._create_expense(mission, etype, 10.0)
            self.assertEqual(expense.expense_type, etype)
            expense.unlink()

    def test_expense_requires_positive_amount(self):
        """Expense amount must be positive."""
        mission = self._create_mission()
        
        with self.assertRaises(ValidationError):
            self._create_expense(mission, 'toll', -50.0)

    def test_expense_requires_amount_greater_than_zero(self):
        """Expense amount must be greater than zero."""
        mission = self._create_mission()
        
        with self.assertRaises(ValidationError):
            self._create_expense(mission, 'toll', 0.0)

    def test_mission_total_expenses_computed(self):
        """Mission should compute total expenses from all linked expenses."""
        mission = self._create_mission()
        self.assertEqual(mission.total_expenses, 0.0)
        
        self._create_expense(mission, 'toll', 50.0)
        self._create_expense(mission, 'fuel', 150.0)
        self._create_expense(mission, 'parking', 20.0)
        
        # Refresh the computed field
        mission.invalidate_recordset(['total_expenses'])
        self.assertEqual(mission.total_expenses, 220.0)

    def test_mission_expense_count_computed(self):
        """Mission should compute expense count."""
        mission = self._create_mission()
        self.assertEqual(mission.expense_count, 0)
        
        self._create_expense(mission, 'toll', 50.0)
        self._create_expense(mission, 'fuel', 150.0)
        
        mission.invalidate_recordset(['expense_count'])
        self.assertEqual(mission.expense_count, 2)

    def test_expense_deletion_updates_total(self):
        """Deleting an expense should update mission total."""
        mission = self._create_mission()
        e1 = self._create_expense(mission, 'toll', 50.0)
        e2 = self._create_expense(mission, 'fuel', 150.0)
        
        mission.invalidate_recordset(['total_expenses'])
        self.assertEqual(mission.total_expenses, 200.0)
        
        e1.unlink()
        mission.invalidate_recordset(['total_expenses'])
        self.assertEqual(mission.total_expenses, 150.0)

    # ========== FR-015: Cost per Kilometer Calculation ==========

    def test_cost_per_km_computed_correctly(self):
        """Cost per km should be total_expenses / distance_km."""
        mission = self._create_mission()
        mission.write({
            'odo_start': 10000.0,
            'odo_end': 10500.0,  # 500 km
        })
        
        self._create_expense(mission, 'toll', 100.0)
        self._create_expense(mission, 'fuel', 150.0)  # Total: 250
        
        mission.invalidate_recordset(['cost_per_km', 'distance_km', 'total_expenses'])
        
        # 250 / 500 = 0.5 per km
        self.assertAlmostEqual(mission.cost_per_km, 0.5, places=2)

    def test_cost_per_km_zero_when_no_distance(self):
        """Cost per km should be 0.0 when distance is zero or not calculable."""
        mission = self._create_mission()
        # No odometer readings
        
        self._create_expense(mission, 'toll', 100.0)
        
        mission.invalidate_recordset(['cost_per_km', 'distance_km', 'total_expenses'])
        self.assertEqual(mission.cost_per_km, 0.0)

    def test_cost_per_km_zero_when_no_expenses(self):
        """Cost per km should be 0.0 when there are no expenses."""
        mission = self._create_mission()
        mission.write({
            'odo_start': 10000.0,
            'odo_end': 10500.0,
        })
        
        mission.invalidate_recordset(['cost_per_km', 'distance_km', 'total_expenses'])
        self.assertEqual(mission.cost_per_km, 0.0)

    def test_cost_per_km_non_blocking(self):
        """Cost per km calculation should never block workflow."""
        mission = self._create_mission()
        # No odometer readings - workflow should proceed
        
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')
        
        # Access cost_per_km shouldn't raise
        _ = mission.cost_per_km

    # ========== FR-026: Analytic Propagation ==========

    def test_expense_with_analytic_account(self):
        """Expense can have an analytic account assigned."""
        if not self.analytic_account:
            self.skipTest("Analytic module not available")
        
        mission = self._create_mission()
        expense = self._create_expense(
            mission, 'toll', 100.0,
            analytic_account_id=self.analytic_account.id
        )
        
        self.assertEqual(expense.analytic_account_id, self.analytic_account)

    def test_mission_inherits_analytic_from_vehicle(self):
        """Mission can inherit analytic account from vehicle (if configured)."""
        # This tests the optional analytic propagation behavior
        # Implementation may vary based on configuration
        mission = self._create_mission()
        # Basic test - mission should not fail if analytic is not set
        self.assertFalse(mission.analytic_account_id if hasattr(mission, 'analytic_account_id') else False)

    def test_expense_grouped_by_type(self):
        """Mission should be able to report expenses grouped by type."""
        mission = self._create_mission()
        
        self._create_expense(mission, 'toll', 50.0)
        self._create_expense(mission, 'toll', 30.0)
        self._create_expense(mission, 'fuel', 150.0)
        self._create_expense(mission, 'parking', 20.0)
        
        # Test grouping via read_group
        Expense = self.env['fleet.mission.expense']
        grouped = Expense.read_group(
            domain=[('mission_id', '=', mission.id)],
            fields=['expense_type', 'amount:sum'],
            groupby=['expense_type'],
        )
        
        totals = {g['expense_type']: g['amount'] for g in grouped}
        self.assertEqual(totals.get('toll'), 80.0)
        self.assertEqual(totals.get('fuel'), 150.0)
        self.assertEqual(totals.get('parking'), 20.0)

    # ========== Expense Reference Sequence ==========

    def test_expense_auto_generates_name(self):
        """Expense should auto-generate a reference name."""
        mission = self._create_mission()
        expense = self._create_expense(mission, 'toll', 100.0)
        
        self.assertTrue(expense.name)
        self.assertTrue(expense.name.startswith('EXP-'))

    def test_expense_name_unique(self):
        """Each expense should have a unique reference."""
        mission = self._create_mission()
        e1 = self._create_expense(mission, 'toll', 100.0)
        e2 = self._create_expense(mission, 'toll', 100.0)
        
        self.assertNotEqual(e1.name, e2.name)

    # ========== Expense Date Validation ==========

    def test_expense_date_required(self):
        """Expense date should be required."""
        mission = self._create_mission()
        
        # Try creating without date (should use default)
        expense = self.env['fleet.mission.expense'].create({
            'mission_id': mission.id,
            'expense_type': 'toll',
            'amount': 100.0,
            'description': 'Test expense',
        })
        
        self.assertTrue(expense.date)

    def test_expense_can_have_future_date(self):
        """Expense can have a future date (for planned expenses)."""
        mission = self._create_mission()
        future_date = datetime.now().date() + timedelta(days=30)
        
        expense = self._create_expense(mission, 'toll', 100.0, date=future_date)
        self.assertEqual(expense.date, future_date)

    # ========== Expense Vendor/Partner ==========

    def test_expense_can_have_vendor(self):
        """Expense can have an optional vendor/partner."""
        mission = self._create_mission()
        vendor = self.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })
        
        expense = self._create_expense(mission, 'toll', 100.0, vendor_id=vendor.id)
        self.assertEqual(expense.vendor_id, vendor)

    def test_expense_vendor_optional(self):
        """Expense vendor should be optional."""
        mission = self._create_mission()
        expense = self._create_expense(mission, 'toll', 100.0)
        
        self.assertFalse(expense.vendor_id)

    # ========== Edge Cases ==========

    def test_many_expenses_performance(self):
        """Should handle many expenses efficiently."""
        mission = self._create_mission()
        
        # Create 100 expenses
        for i in range(100):
            self._create_expense(mission, 'toll', 1.0)
        
        mission.invalidate_recordset(['total_expenses', 'expense_count'])
        self.assertEqual(mission.total_expenses, 100.0)
        self.assertEqual(mission.expense_count, 100)

    def test_decimal_amounts_handled(self):
        """Should handle decimal amounts correctly."""
        mission = self._create_mission()
        
        self._create_expense(mission, 'toll', 33.33)
        self._create_expense(mission, 'toll', 33.33)
        self._create_expense(mission, 'toll', 33.34)
        
        mission.invalidate_recordset(['total_expenses'])
        self.assertAlmostEqual(mission.total_expenses, 100.0, places=2)
