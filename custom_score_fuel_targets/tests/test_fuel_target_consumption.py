# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for fuel consumption target comparison and alert determination (FR-024/FR-025).

Test coverage:
- Target consumption per vehicle category (family)
- Comparison of actual L/100km vs target
- Alert determination (ok/warning/critical)
- Handling of "non-calculable" when distance is 0 or missing
- Summary target variance computation
"""

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestFuelTargetConsumption(TransactionCase):
    """Test suite for fuel consumption targets (FR-024)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create vehicle category with target
        cls.category_poids_lourd = cls.env['fleet.vehicle.model.category'].create({
            'name': 'Poids Lourds',
            'target_consumption_l100km': 35.0,  # 35 L/100km target
        })
        
        cls.category_vehicule_leger = cls.env['fleet.vehicle.model.category'].create({
            'name': 'Véhicules Légers',
            'target_consumption_l100km': 8.0,  # 8 L/100km target
        })
        
        cls.category_no_target = cls.env['fleet.vehicle.model.category'].create({
            'name': 'Sans Cible',
            # No target defined
        })
        
        # Create vehicle model and brand
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Fuel',
        })
        
        cls.model_poids_lourd = cls.env['fleet.vehicle.model'].create({
            'name': 'Camion Test',
            'brand_id': cls.brand.id,
            'category_id': cls.category_poids_lourd.id,
        })
        
        cls.model_leger = cls.env['fleet.vehicle.model'].create({
            'name': 'Berline Test',
            'brand_id': cls.brand.id,
            'category_id': cls.category_vehicule_leger.id,
        })
        
        # Create test vehicles
        cls.vehicle_truck = cls.env['fleet.vehicle'].create({
            'model_id': cls.model_poids_lourd.id,
            'license_plate': 'FUEL-PL-001',
            'company_id': cls.env.company.id,
        })
        
        cls.vehicle_car = cls.env['fleet.vehicle'].create({
            'model_id': cls.model_leger.id,
            'license_plate': 'FUEL-VL-001',
            'company_id': cls.env.company.id,
        })
        
        # Reference to models
        cls.Summary = cls.env['fleet.fuel.monthly.summary']
        cls.Category = cls.env['fleet.vehicle.model.category']

    def test_category_has_target_field(self):
        """Test that category model has target_consumption_l100km field."""
        self.assertTrue(hasattr(self.category_poids_lourd, 'target_consumption_l100km'))
        self.assertEqual(self.category_poids_lourd.target_consumption_l100km, 35.0)

    def test_category_target_positive_constraint(self):
        """Test that target consumption must be positive or zero."""
        with self.assertRaises(ValidationError):
            self.env['fleet.vehicle.model.category'].create({
                'name': 'Invalid Target',
                'target_consumption_l100km': -5.0,
            })

    def test_vehicle_inherits_target_from_category(self):
        """Test that vehicle can access target via its category."""
        # Access via model_id.category_id
        target = self.vehicle_truck.category_id.target_consumption_l100km
        self.assertEqual(target, 35.0)

    def test_summary_target_variance_below_target(self):
        """Test variance is negative when consumption is below target."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-BELOW-TARGET',
            'vehicle_id': self.vehicle_truck.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 10000,
            'odometer_end': 10500,  # 500 km traveled
            'company_id': self.env.company.id,
        })
        # Simulate 150 liters consumed → 30 L/100km (below 35 target)
        summary.write({'total_liter': 150.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        # avg_consumption = 150 / 500 * 100 = 30 L/100km
        # variance = 30 - 35 = -5 (economy)
        self.assertAlmostEqual(summary.avg_consumption_per_100km, 30.0, places=1)
        self.assertAlmostEqual(summary.target_consumption_l100km, 35.0, places=1)
        self.assertAlmostEqual(summary.target_variance_l100km, -5.0, places=1)

    def test_summary_target_variance_above_target(self):
        """Test variance is positive when consumption exceeds target."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-ABOVE-TARGET',
            'vehicle_id': self.vehicle_car.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 50000,
            'odometer_end': 50500,  # 500 km traveled
            'company_id': self.env.company.id,
        })
        # Simulate 60 liters consumed → 12 L/100km (above 8 target)
        summary.write({'total_liter': 60.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        # avg_consumption = 60 / 500 * 100 = 12 L/100km
        # variance = 12 - 8 = +4 (over-consumption)
        self.assertAlmostEqual(summary.avg_consumption_per_100km, 12.0, places=1)
        self.assertAlmostEqual(summary.target_consumption_l100km, 8.0, places=1)
        self.assertAlmostEqual(summary.target_variance_l100km, 4.0, places=1)

    def test_summary_variance_zero_when_no_target(self):
        """Test variance is 0 when category has no target defined."""
        # Create vehicle with no-target category
        model_no_target = self.env['fleet.vehicle.model'].create({
            'name': 'Model Sans Cible',
            'brand_id': self.brand.id,
            'category_id': self.category_no_target.id,
        })
        vehicle_no_target = self.env['fleet.vehicle'].create({
            'model_id': model_no_target.id,
            'license_plate': 'FUEL-NT-001',
            'company_id': self.env.company.id,
        })
        
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-NO-TARGET',
            'vehicle_id': vehicle_no_target.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 1000,
            'odometer_end': 1100,
            'company_id': self.env.company.id,
        })
        summary.write({'total_liter': 10.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        self.assertFalse(summary.target_consumption_l100km)
        self.assertEqual(summary.target_variance_l100km, 0.0)


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestFuelConsumptionAlerts(TransactionCase):
    """Test suite for over-consumption alerts (FR-025)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create category with 10 L/100km target
        cls.category = cls.env['fleet.vehicle.model.category'].create({
            'name': 'Test Category Alert',
            'target_consumption_l100km': 10.0,
        })
        
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Alert',
        })
        
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Alert',
            'brand_id': cls.brand.id,
            'category_id': cls.category.id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'ALERT-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Summary = cls.env['fleet.fuel.monthly.summary']

    def _create_summary_with_consumption(self, consumption_l100km):
        """Helper to create summary with specific consumption."""
        today = date.today()
        summary = self.Summary.create({
            'name': f'TEST-ALERT-{consumption_l100km}',
            'vehicle_id': self.vehicle.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 1000,
            'odometer_end': 1100,  # 100 km
            'company_id': self.env.company.id,
        })
        # Set liters to achieve desired L/100km
        # consumption_l100km = liters / 100 * 100 = liters
        summary.write({'total_liter': consumption_l100km})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        summary._compute_consumption_alert_level()
        return summary

    def test_alert_ok_when_at_target(self):
        """Test alert is 'ok' when consumption equals target."""
        summary = self._create_summary_with_consumption(10.0)  # Exactly at target
        self.assertEqual(summary.consumption_alert_level, 'ok')

    def test_alert_ok_when_below_target(self):
        """Test alert is 'ok' when consumption is below target."""
        summary = self._create_summary_with_consumption(8.0)  # 20% below target
        self.assertEqual(summary.consumption_alert_level, 'ok')

    def test_alert_warning_when_slightly_above(self):
        """Test alert is 'warning' when consumption is slightly above target."""
        # Default threshold is 10% - so 11 L/100km should be warning
        summary = self._create_summary_with_consumption(11.0)  # 10% above
        self.assertEqual(summary.consumption_alert_level, 'warning')

    def test_alert_critical_when_significantly_above(self):
        """Test alert is 'critical' when consumption exceeds 2x threshold."""
        # Default threshold is 10% - so >20% above should be critical
        summary = self._create_summary_with_consumption(13.0)  # 30% above
        self.assertEqual(summary.consumption_alert_level, 'critical')

    def test_alert_not_calculable_when_no_distance(self):
        """Test alert is 'non_calculable' when distance is 0."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-NO-DISTANCE',
            'vehicle_id': self.vehicle.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 1000,
            'odometer_end': 1000,  # 0 km
            'company_id': self.env.company.id,
        })
        summary.write({'total_liter': 50.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        summary._compute_consumption_alert_level()
        
        # L/100km cannot be calculated without distance
        self.assertEqual(summary.consumption_alert_level, 'non_calculable')

    def test_alert_not_calculable_when_no_liters(self):
        """Test alert is 'non_calculable' when liters is 0."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-NO-LITERS',
            'vehicle_id': self.vehicle.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 1000,
            'odometer_end': 1100,
            'company_id': self.env.company.id,
        })
        # No liters set
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        summary._compute_consumption_alert_level()
        
        self.assertEqual(summary.consumption_alert_level, 'non_calculable')

    def test_alert_not_calculable_when_no_target(self):
        """Test alert is 'non_calculable' when category has no target."""
        # Create vehicle without target
        category_no_target = self.env['fleet.vehicle.model.category'].create({
            'name': 'No Target Category',
        })
        model_no_target = self.env['fleet.vehicle.model'].create({
            'name': 'No Target Model',
            'brand_id': self.brand.id,
            'category_id': category_no_target.id,
        })
        vehicle_no_target = self.env['fleet.vehicle'].create({
            'model_id': model_no_target.id,
            'license_plate': 'NO-TARGET-001',
            'company_id': self.env.company.id,
        })
        
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-NO-TARGET-ALERT',
            'vehicle_id': vehicle_no_target.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 1000,
            'odometer_end': 1100,
            'company_id': self.env.company.id,
        })
        summary.write({'total_liter': 10.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        summary._compute_consumption_alert_level()
        
        self.assertEqual(summary.consumption_alert_level, 'non_calculable')


@tagged('post_install', '-at_install', 'score_fuel_targets')
class TestFuelTargetVariancePercent(TransactionCase):
    """Test suite for variance percentage calculations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.category = cls.env['fleet.vehicle.model.category'].create({
            'name': 'Variance Test Category',
            'target_consumption_l100km': 20.0,
        })
        
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Variance Test Brand',
        })
        
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Variance Test Model',
            'brand_id': cls.brand.id,
            'category_id': cls.category.id,
        })
        
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'VAR-001',
            'company_id': cls.env.company.id,
        })
        
        cls.Summary = cls.env['fleet.fuel.monthly.summary']

    def test_variance_percent_positive(self):
        """Test variance percentage when over-consuming."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-VAR-POS',
            'vehicle_id': self.vehicle.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 0,
            'odometer_end': 100,  # 100 km
            'company_id': self.env.company.id,
        })
        # 25 L / 100 km = 25 L/100km (vs 20 target = +25%)
        summary.write({'total_liter': 25.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        self.assertAlmostEqual(summary.target_variance_pct, 25.0, places=1)

    def test_variance_percent_negative(self):
        """Test variance percentage when under-consuming (economy)."""
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-VAR-NEG',
            'vehicle_id': self.vehicle.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 0,
            'odometer_end': 100,  # 100 km
            'company_id': self.env.company.id,
        })
        # 16 L / 100 km = 16 L/100km (vs 20 target = -20%)
        summary.write({'total_liter': 16.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        self.assertAlmostEqual(summary.target_variance_pct, -20.0, places=1)

    def test_variance_percent_zero_when_no_target(self):
        """Test variance percentage is 0 when no target defined."""
        category_no_target = self.env['fleet.vehicle.model.category'].create({
            'name': 'No Target Var',
        })
        model_no_target = self.env['fleet.vehicle.model'].create({
            'name': 'No Target Var Model',
            'brand_id': self.brand.id,
            'category_id': category_no_target.id,
        })
        vehicle_no_target = self.env['fleet.vehicle'].create({
            'model_id': model_no_target.id,
            'license_plate': 'VAR-NT-001',
            'company_id': self.env.company.id,
        })
        
        today = date.today()
        summary = self.Summary.create({
            'name': 'TEST-VAR-NT',
            'vehicle_id': vehicle_no_target.id,
            'period_start': today.replace(day=1),
            'period_end': today,
            'odometer_start': 0,
            'odometer_end': 100,
            'company_id': self.env.company.id,
        })
        summary.write({'total_liter': 15.0})
        summary._compute_distance_kpi()
        summary._compute_target_variance()
        
        self.assertEqual(summary.target_variance_pct, 0.0)
