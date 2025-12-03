# -*- coding: utf-8 -*-
"""Tests for fleet.fuel.monthly.summary model and KPI service.

Test coverage:
- CRUD operations and sequence generation
- Consumption totals computation (total_amount, total_liter)
- L/100km consumption calculation (avg_consumption_per_100km)
- Budget variance calculation
- Alert level determination (ok/warning/critical)
- Workflow: draft -> confirmed -> closed
- KPI service methods
- Cron job methods
"""
import base64
import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestFleetFuelSummary(TransactionCase):
    """Test cases for fleet.fuel.monthly.summary model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for fuel summary tests."""
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        cls.currency = cls.company.currency_id

        # Create vehicle brand and model
        cls.vehicle_brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Summary Test Brand',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Summary Test Model',
            'brand_id': cls.vehicle_brand.id,
        })

        # Create test vehicles
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'SUMMARY-001',
            'company_id': cls.company.id,
        })
        cls.vehicle_2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'SUMMARY-002',
            'company_id': cls.company.id,
        })

        # Create test driver
        cls.driver = cls.env['hr.employee'].create({
            'name': 'Summary Test Driver',
            'company_id': cls.company.id,
        })

        # Create test fuel card
        cls.card = cls.env['fleet.fuel.card'].create({
            'card_uid': 'SUMMARY-CARD-001',
            'vehicle_id': cls.vehicle.id,
            'driver_id': cls.driver.id,
            'balance_amount': 10000.0,
            'company_id': cls.company.id,
        })
        cls.card.action_activate()

        # Create second card
        cls.card_2 = cls.env['fleet.fuel.card'].create({
            'card_uid': 'SUMMARY-CARD-002',
            'vehicle_id': cls.vehicle_2.id,
            'balance_amount': 5000.0,
            'company_id': cls.company.id,
        })
        cls.card_2.action_activate()

        # Dummy receipt for expenses
        cls.dummy_receipt = base64.b64encode(b'Test receipt for summary tests')

        # Set up test period
        cls.today = fields.Date.context_today(cls.env.user)
        cls.period_start = cls.today.replace(day=1)
        cls.period_end = (cls.period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        cls.Summary = cls.env['fleet.fuel.monthly.summary']
        cls.Expense = cls.env['fleet.fuel.expense']
        cls.Recharge = cls.env['fleet.fuel.recharge']
        cls.KPIService = cls.env['fleet.fuel.kpi.service']

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _create_summary(self, vehicle=None, card=None, **kwargs):
        """Helper to create summary with default values."""
        vals = {
            'period_start': self.period_start,
            'period_end': self.period_end,
            'vehicle_id': (vehicle or self.vehicle).id if vehicle or 'vehicle_id' not in kwargs else kwargs.get('vehicle_id'),
            'card_id': (card or self.card).id if card or 'card_id' not in kwargs else kwargs.get('card_id'),
            'company_id': self.company.id,
            'currency_id': self.currency.id,
        }
        vals.update(kwargs)
        return self.Summary.create(vals)

    def _create_validated_expense(self, card=None, vehicle=None, amount=100.0,
                                   liter_qty=25.0, odometer=None, expense_date=None):
        """Helper to create and validate an expense."""
        expense = self.Expense.create({
            'card_id': (card or self.card).id,
            'vehicle_id': (vehicle or self.vehicle).id,
            'amount': amount,
            'liter_qty': liter_qty,
            'odometer': odometer or 0.0,
            'expense_date': expense_date or self.today,
            'receipt_attachment': self.dummy_receipt,
            'company_id': self.company.id,
        })
        expense.action_validate()
        return expense

    def _create_posted_recharge(self, card=None, amount=500.0, recharge_date=None):
        """Helper to create and post a recharge."""
        recharge = self.Recharge.create({
            'card_id': (card or self.card).id,
            'amount': amount,
            'recharge_date': recharge_date or self.today,
        })
        recharge.action_submit()
        recharge.action_approve()
        recharge.action_post()
        return recharge

    # -------------------------------------------------------------------------
    # TEST: BASIC CRUD OPERATIONS
    # -------------------------------------------------------------------------
    def test_01_summary_creation_basic(self):
        """Test basic summary creation with auto-generated sequence."""
        summary = self._create_summary()

        self.assertTrue(summary.exists())
        self.assertEqual(summary.state, 'draft')
        self.assertTrue(summary.name, "Summary name should be auto-generated")
        self.assertEqual(summary.vehicle_id, self.vehicle)
        self.assertEqual(summary.card_id, self.card)
        self.assertEqual(summary.company_id, self.company)
        self.assertEqual(summary.currency_id, self.currency)

    def test_02_summary_creation_minimal(self):
        """Test summary creation with minimal data (no vehicle/card)."""
        summary = self.Summary.create({
            'period_start': self.period_start,
            'period_end': self.period_end,
            'company_id': self.company.id,
        })

        self.assertTrue(summary.exists())
        self.assertFalse(summary.vehicle_id)
        self.assertFalse(summary.card_id)

    def test_03_summary_creation_with_driver(self):
        """Test summary creation with driver assigned."""
        summary = self._create_summary(driver_id=self.driver.id)

        self.assertEqual(summary.driver_id, self.driver)

    def test_04_summary_creation_with_budget(self):
        """Test summary creation with budget amount."""
        summary = self._create_summary(budget_amount=2000.0)

        self.assertEqual(summary.budget_amount, 2000.0)

    # -------------------------------------------------------------------------
    # TEST: PERIOD DATE CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_05_summary_period_dates_valid(self):
        """Test valid period dates (end >= start)."""
        summary = self._create_summary(
            period_start='2025-01-01',
            period_end='2025-01-31',
        )

        self.assertTrue(summary.exists())

    def test_06_summary_period_dates_same_day(self):
        """Test valid period with same start and end date."""
        summary = self._create_summary(
            period_start='2025-01-15',
            period_end='2025-01-15',
        )

        self.assertTrue(summary.exists())

    def test_07_summary_period_dates_invalid(self):
        """Test that end before start raises error."""
        with self.assertRaises(ValidationError):
            self._create_summary(
                period_start='2025-01-31',
                period_end='2025-01-01',
            )

    # -------------------------------------------------------------------------
    # TEST: ODOMETER CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_08_summary_odometer_valid(self):
        """Test valid odometer values (end >= start)."""
        summary = self._create_summary(
            odometer_start=10000.0,
            odometer_end=12000.0,
        )

        self.assertEqual(summary.odometer_start, 10000.0)
        self.assertEqual(summary.odometer_end, 12000.0)

    def test_09_summary_odometer_negative_start_fails(self):
        """Test that negative odometer start raises error."""
        with self.assertRaises(ValidationError):
            self._create_summary(odometer_start=-100.0)

    def test_10_summary_odometer_negative_end_fails(self):
        """Test that negative odometer end raises error."""
        with self.assertRaises(ValidationError):
            self._create_summary(odometer_end=-100.0)

    def test_11_summary_odometer_end_less_than_start_fails(self):
        """Test that odometer_end < odometer_start raises error."""
        with self.assertRaises(ValidationError):
            self._create_summary(
                odometer_start=15000.0,
                odometer_end=10000.0,
            )

    # -------------------------------------------------------------------------
    # TEST: CONSUMPTION TOTALS COMPUTATION
    # -------------------------------------------------------------------------
    def test_12_summary_consumption_totals_empty(self):
        """Test consumption totals with no expenses."""
        summary = self._create_summary()

        self.assertEqual(summary.total_amount, 0.0)
        self.assertEqual(summary.total_liter, 0.0)
        self.assertEqual(summary.expense_count, 0)

    def test_13_summary_consumption_totals_with_expenses(self):
        """Test consumption totals with validated expenses."""
        # Create validated expenses
        self._create_validated_expense(amount=100.0, liter_qty=25.0)
        self._create_validated_expense(amount=150.0, liter_qty=40.0)
        self._create_validated_expense(amount=200.0, liter_qty=50.0)

        summary = self._create_summary()
        summary.invalidate_recordset(['total_amount', 'total_liter', 'expense_count'])

        self.assertEqual(summary.total_amount, 450.0)  # 100 + 150 + 200
        self.assertEqual(summary.total_liter, 115.0)   # 25 + 40 + 50
        self.assertEqual(summary.expense_count, 3)

    def test_14_summary_recharge_totals(self):
        """Test recharge totals with posted recharges."""
        # Create posted recharges
        self._create_posted_recharge(amount=500.0)
        self._create_posted_recharge(amount=300.0)

        summary = self._create_summary()
        summary.invalidate_recordset(['total_recharge_amount', 'recharge_count'])

        self.assertEqual(summary.total_recharge_amount, 800.0)
        self.assertEqual(summary.recharge_count, 2)

    # -------------------------------------------------------------------------
    # TEST: DISTANCE AND L/100KM COMPUTATION
    # -------------------------------------------------------------------------
    def test_15_summary_distance_traveled(self):
        """Test distance_traveled computation."""
        summary = self._create_summary(
            odometer_start=10000.0,
            odometer_end=10500.0,
        )

        self.assertEqual(summary.distance_traveled, 500.0)

    def test_16_summary_distance_zero_when_no_odometer(self):
        """Test distance is zero when no odometer values."""
        summary = self._create_summary()

        self.assertEqual(summary.distance_traveled, 0.0)

    def test_17_summary_l_per_100km_computation(self):
        """Test avg_consumption_per_100km calculation."""
        # Create expense
        self._create_validated_expense(amount=100.0, liter_qty=50.0)

        summary = self._create_summary(
            odometer_start=10000.0,
            odometer_end=10500.0,  # 500 km traveled
        )
        summary.invalidate_recordset(['avg_consumption_per_100km', 'total_liter', 'distance_traveled'])

        # 50 liters / 500 km * 100 = 10 L/100km
        self.assertEqual(summary.avg_consumption_per_100km, 10.0)

    def test_18_summary_l_per_100km_zero_distance(self):
        """Test L/100km is zero when no distance."""
        self._create_validated_expense(amount=100.0, liter_qty=50.0)

        summary = self._create_summary(
            odometer_start=10000.0,
            odometer_end=10000.0,  # No distance
        )
        summary.invalidate_recordset(['avg_consumption_per_100km'])

        self.assertEqual(summary.avg_consumption_per_100km, 0.0)

    def test_19_summary_l_per_100km_zero_liters(self):
        """Test L/100km is zero when no liters."""
        summary = self._create_summary(
            odometer_start=10000.0,
            odometer_end=10500.0,
        )

        self.assertEqual(summary.avg_consumption_per_100km, 0.0)

    # -------------------------------------------------------------------------
    # TEST: AVERAGE PRICE PER LITER
    # -------------------------------------------------------------------------
    def test_20_summary_avg_price_per_liter(self):
        """Test average price per liter computation."""
        self._create_validated_expense(amount=200.0, liter_qty=50.0)

        summary = self._create_summary()
        summary.invalidate_recordset(['avg_price_per_liter'])

        self.assertEqual(summary.avg_price_per_liter, 4.0)  # 200 / 50

    def test_21_summary_avg_price_zero_liters(self):
        """Test avg price is zero when no liters."""
        summary = self._create_summary()

        self.assertEqual(summary.avg_price_per_liter, 0.0)

    # -------------------------------------------------------------------------
    # TEST: BUDGET VARIANCE COMPUTATION
    # -------------------------------------------------------------------------
    def test_22_summary_budget_variance_under_budget(self):
        """Test budget variance when under budget (saving)."""
        self._create_validated_expense(amount=800.0, liter_qty=200.0)

        summary = self._create_summary(budget_amount=1000.0)
        summary.invalidate_recordset(['budget_variance', 'variance_pct'])

        self.assertEqual(summary.budget_variance, -200.0)  # 800 - 1000 = -200 (saving)
        self.assertEqual(summary.variance_pct, -20.0)      # -200 / 1000 * 100

    def test_23_summary_budget_variance_over_budget(self):
        """Test budget variance when over budget (overspend)."""
        self._create_validated_expense(amount=1200.0, liter_qty=300.0)

        summary = self._create_summary(budget_amount=1000.0)
        summary.invalidate_recordset(['budget_variance', 'variance_pct'])

        self.assertEqual(summary.budget_variance, 200.0)   # 1200 - 1000 = 200 (overspend)
        self.assertEqual(summary.variance_pct, 20.0)       # 200 / 1000 * 100

    def test_24_summary_budget_variance_no_budget(self):
        """Test variance is zero when no budget set."""
        self._create_validated_expense(amount=500.0, liter_qty=125.0)

        summary = self._create_summary(budget_amount=0.0)
        summary.invalidate_recordset(['budget_variance', 'variance_pct'])

        self.assertEqual(summary.budget_variance, 0.0)
        self.assertEqual(summary.variance_pct, 0.0)

    # -------------------------------------------------------------------------
    # TEST: ALERT LEVEL DETERMINATION
    # -------------------------------------------------------------------------
    def test_25_summary_alert_level_ok(self):
        """Test alert level is 'ok' when variance is low."""
        # Set threshold to 10%
        self.env['ir.config_parameter'].sudo().set_param(
            'fleet_fuel.variance_threshold_pct', '10.0'
        )

        self._create_validated_expense(amount=1050.0, liter_qty=250.0)

        summary = self._create_summary(budget_amount=1000.0)
        summary.invalidate_recordset(['alert_level', 'variance_pct'])

        # 5% variance should be OK (under 10% threshold)
        self.assertEqual(summary.alert_level, 'ok')

    def test_26_summary_alert_level_warning(self):
        """Test alert level is 'warning' when variance is medium."""
        self.env['ir.config_parameter'].sudo().set_param(
            'fleet_fuel.variance_threshold_pct', '10.0'
        )

        self._create_validated_expense(amount=1150.0, liter_qty=280.0)

        summary = self._create_summary(budget_amount=1000.0)
        summary.invalidate_recordset(['alert_level', 'variance_pct'])

        # 15% variance should be Warning (between 10% and 20%)
        self.assertEqual(summary.alert_level, 'warning')

    def test_27_summary_alert_level_critical(self):
        """Test alert level is 'critical' when variance is high."""
        self.env['ir.config_parameter'].sudo().set_param(
            'fleet_fuel.variance_threshold_pct', '10.0'
        )

        self._create_validated_expense(amount=1300.0, liter_qty=325.0)

        summary = self._create_summary(budget_amount=1000.0)
        summary.invalidate_recordset(['alert_level', 'variance_pct'])

        # 30% variance should be Critical (over 20% = 2x threshold)
        self.assertEqual(summary.alert_level, 'critical')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - CONFIRM
    # -------------------------------------------------------------------------
    def test_28_summary_confirm_workflow(self):
        """Test summary confirmation workflow."""
        summary = self._create_summary()
        self.assertEqual(summary.state, 'draft')

        summary.action_confirm()

        self.assertEqual(summary.state, 'confirmed')

    def test_29_summary_confirm_idempotent(self):
        """Test confirming already confirmed summary does nothing."""
        summary = self._create_summary()
        summary.action_confirm()

        # Confirm again
        summary.action_confirm()

        self.assertEqual(summary.state, 'confirmed')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - CLOSE
    # -------------------------------------------------------------------------
    def test_30_summary_close_workflow(self):
        """Test summary closure workflow."""
        summary = self._create_summary()
        summary.action_confirm()

        summary.action_close()

        self.assertEqual(summary.state, 'closed')

    def test_31_summary_close_requires_confirm(self):
        """Test that closing requires confirmed state."""
        summary = self._create_summary()

        # Try to close from draft (should not change state)
        summary.action_close()

        self.assertEqual(summary.state, 'draft')

    # -------------------------------------------------------------------------
    # TEST: WORKFLOW - RESET TO DRAFT
    # -------------------------------------------------------------------------
    def test_32_summary_reset_to_draft(self):
        """Test resetting confirmed summary to draft."""
        summary = self._create_summary()
        summary.action_confirm()

        summary.action_reset_to_draft()

        self.assertEqual(summary.state, 'draft')

    def test_33_summary_reset_closed_no_effect(self):
        """Test that resetting closed summary has no effect."""
        summary = self._create_summary()
        summary.action_confirm()
        summary.action_close()

        summary.action_reset_to_draft()

        self.assertEqual(summary.state, 'closed')

    # -------------------------------------------------------------------------
    # TEST: RECALCULATE ACTION
    # -------------------------------------------------------------------------
    def test_34_summary_recalculate(self):
        """Test recalculate action triggers recomputation."""
        summary = self._create_summary()
        initial_amount = summary.total_amount

        # Add expense
        self._create_validated_expense(amount=300.0, liter_qty=75.0)

        # Recalculate
        summary.action_recalculate()
        summary.invalidate_recordset(['total_amount'])

        self.assertEqual(summary.total_amount, initial_amount + 300.0)

    # -------------------------------------------------------------------------
    # TEST: AUTO-FILL ODOMETER ACTION
    # -------------------------------------------------------------------------
    def test_35_summary_auto_fill_odometer(self):
        """Test auto-fill odometer from expenses."""
        # Create expenses with odometer readings
        self._create_validated_expense(
            amount=100.0, liter_qty=25.0, odometer=10000.0
        )
        self._create_validated_expense(
            amount=150.0, liter_qty=40.0, odometer=10300.0
        )
        self._create_validated_expense(
            amount=200.0, liter_qty=50.0, odometer=10600.0
        )

        summary = self._create_summary()
        summary.action_auto_fill_odometer()

        self.assertEqual(summary.odometer_start, 10000.0)
        self.assertEqual(summary.odometer_end, 10600.0)

    def test_36_summary_auto_fill_odometer_no_vehicle(self):
        """Test auto-fill odometer does nothing without vehicle."""
        summary = self._create_summary(vehicle_id=False)

        # Should not raise error
        summary.action_auto_fill_odometer()

        self.assertEqual(summary.odometer_start, 0.0)
        self.assertEqual(summary.odometer_end, 0.0)

    # -------------------------------------------------------------------------
    # TEST: KPI SERVICE METHODS
    # -------------------------------------------------------------------------
    def test_37_kpi_service_compute_l_per_100km(self):
        """Test KPI service compute_l_per_100km method."""
        result = self.KPIService.compute_l_per_100km(liters=50.0, distance=500.0)
        self.assertEqual(result, 10.0)

    def test_38_kpi_service_compute_l_per_100km_zero_distance(self):
        """Test compute_l_per_100km with zero distance."""
        result = self.KPIService.compute_l_per_100km(liters=50.0, distance=0.0)
        self.assertEqual(result, 0.0)

    def test_39_kpi_service_compute_l_per_100km_zero_liters(self):
        """Test compute_l_per_100km with zero liters."""
        result = self.KPIService.compute_l_per_100km(liters=0.0, distance=500.0)
        self.assertEqual(result, 0.0)

    def test_40_kpi_service_compute_avg_price_per_liter(self):
        """Test KPI service compute_avg_price_per_liter method."""
        result = self.KPIService.compute_avg_price_per_liter(amount=200.0, liters=50.0)
        self.assertEqual(result, 4.0)

    def test_41_kpi_service_compute_budget_variance(self):
        """Test KPI service compute_budget_variance method."""
        variance_amount, variance_pct = self.KPIService.compute_budget_variance(
            actual=1200.0, budget=1000.0
        )

        self.assertEqual(variance_amount, 200.0)
        self.assertEqual(variance_pct, 20.0)

    def test_42_kpi_service_compute_budget_variance_no_budget(self):
        """Test compute_budget_variance with zero budget."""
        variance_amount, variance_pct = self.KPIService.compute_budget_variance(
            actual=500.0, budget=0.0
        )

        self.assertEqual(variance_amount, 0.0)
        self.assertEqual(variance_pct, 0.0)

    def test_43_kpi_service_determine_alert_level_ok(self):
        """Test KPI service determine_alert_level - ok."""
        result = self.KPIService.determine_alert_level(variance_pct=5.0, threshold=10.0)
        self.assertEqual(result, 'ok')

    def test_44_kpi_service_determine_alert_level_warning(self):
        """Test KPI service determine_alert_level - warning."""
        result = self.KPIService.determine_alert_level(variance_pct=15.0, threshold=10.0)
        self.assertEqual(result, 'warning')

    def test_45_kpi_service_determine_alert_level_critical(self):
        """Test KPI service determine_alert_level - critical."""
        result = self.KPIService.determine_alert_level(variance_pct=25.0, threshold=10.0)
        self.assertEqual(result, 'critical')

    def test_46_kpi_service_get_alert_threshold(self):
        """Test KPI service get_alert_threshold method."""
        self.env['ir.config_parameter'].sudo().set_param(
            'fleet_fuel.variance_threshold_pct', '15.0'
        )

        result = self.KPIService.get_alert_threshold()

        self.assertEqual(result, 15.0)

    # -------------------------------------------------------------------------
    # TEST: UNIQUE CONSTRAINT
    # -------------------------------------------------------------------------
    def test_47_summary_unique_constraint(self):
        """Test unique constraint on company/vehicle/card/period."""
        self._create_summary()

        # Try to create duplicate
        with self.assertRaises(Exception):
            self._create_summary()

    def test_48_summary_different_period_allowed(self):
        """Test that different periods are allowed."""
        self._create_summary(
            period_start='2025-01-01',
            period_end='2025-01-31',
        )

        # Different period should work
        summary2 = self._create_summary(
            period_start='2025-02-01',
            period_end='2025-02-28',
        )

        self.assertTrue(summary2.exists())

    # -------------------------------------------------------------------------
    # TEST: BATCH CREATION
    # -------------------------------------------------------------------------
    def test_49_summary_batch_creation(self):
        """Test creating multiple summaries at once."""
        summaries_vals = [
            {
                'period_start': '2025-01-01',
                'period_end': '2025-01-31',
                'vehicle_id': self.vehicle.id,
                'card_id': self.card.id,
                'company_id': self.company.id,
            },
            {
                'period_start': '2025-02-01',
                'period_end': '2025-02-28',
                'vehicle_id': self.vehicle.id,
                'card_id': self.card.id,
                'company_id': self.company.id,
            },
        ]

        summaries = self.Summary.create(summaries_vals)

        self.assertEqual(len(summaries), 2)
        self.assertTrue(all(s.name for s in summaries))

    # -------------------------------------------------------------------------
    # TEST: KPI SERVICE STATISTICS METHODS
    # -------------------------------------------------------------------------
    def test_50_kpi_service_get_consumption_stats(self):
        """Test KPI service get_consumption_stats method."""
        self._create_validated_expense(amount=200.0, liter_qty=50.0)
        self._create_validated_expense(amount=300.0, liter_qty=75.0)

        stats = self.KPIService.get_consumption_stats(
            vehicle_id=self.vehicle.id,
            company_id=self.company.id,
        )

        self.assertEqual(stats['total_amount'], 500.0)
        self.assertEqual(stats['total_liters'], 125.0)
        self.assertEqual(stats['expense_count'], 2)
        self.assertEqual(stats['avg_price_per_liter'], 4.0)

    def test_51_kpi_service_detect_critical_summaries(self):
        """Test KPI service detect_critical_summaries method."""
        # Set threshold and create a summary with high variance
        self.env['ir.config_parameter'].sudo().set_param(
            'fleet_fuel.variance_threshold_pct', '10.0'
        )

        self._create_validated_expense(amount=1500.0, liter_qty=375.0)
        summary = self._create_summary(budget_amount=1000.0)
        summary.action_confirm()
        summary.invalidate_recordset(['alert_level'])

        # Detect critical summaries
        critical = self.KPIService.detect_critical_summaries(days_back=365)

        self.assertIn(summary, critical)

    def test_52_summary_notes_field(self):
        """Test notes HTML field."""
        summary = self._create_summary(
            notes='<p>Monthly fuel consumption analysis</p>'
        )

        self.assertEqual(summary.notes, '<p>Monthly fuel consumption analysis</p>')
