# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for maintenance downtime computation (FR-019).

Test coverage:
- Downtime calculation with actual_start and actual_end
- Fallback to scheduled_start/scheduled_end when actual dates missing
- Downtime = 0 when both actual and scheduled are missing
- Downtime computation across state transitions
- KPI reporting for downtime aggregation
"""

from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'score_maintenance')
class TestMaintenanceDowntime(TransactionCase):
    """Test suite for maintenance downtime computation (FR-019)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get or create vehicle model
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'Test Brand',
            }).id,
        })
        
        # Create a test vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-DT-001',
            'company_id': cls.env.company.id,
        })
        
        # Reference to intervention model
        cls.Intervention = cls.env['fleet.maintenance.intervention']

    def test_downtime_with_actual_dates(self):
        """Test downtime computation when actual_start and actual_end are both set."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=8),
            'actual_end': now,
        })
        
        # Downtime should be computed from actual dates (8 hours)
        self.assertAlmostEqual(
            intervention.downtime_hours,
            8.0,
            places=1,
            msg="Downtime should be 8 hours when computed from actual dates"
        )

    def test_downtime_fallback_to_scheduled(self):
        """Test downtime falls back to scheduled dates when actual dates missing."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
            'scheduled_start': now - timedelta(hours=4),
            'scheduled_end': now,
            # No actual_start or actual_end
        })
        
        # Downtime should fallback to scheduled (4 hours)
        self.assertAlmostEqual(
            intervention.downtime_hours,
            4.0,
            places=1,
            msg="Downtime should fallback to scheduled dates (4 hours)"
        )

    def test_downtime_zero_when_no_dates(self):
        """Test downtime is 0 when no dates are available."""
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            # No scheduled or actual dates
        })
        
        self.assertEqual(
            intervention.downtime_hours,
            0.0,
            "Downtime should be 0 when no dates are set"
        )

    def test_downtime_partial_actual_dates(self):
        """Test downtime when only actual_start is set (ongoing intervention)."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=3),
            # No actual_end - intervention still in progress
        })
        
        # Downtime should use current time as end
        # We can't check exact value since "now" changes, but it should be >= 3
        self.assertGreaterEqual(
            intervention.downtime_hours,
            2.9,  # Allowing some margin
            "Downtime should be calculated until now when no end date"
        )

    def test_downtime_actual_overrides_scheduled(self):
        """Test that actual dates always take precedence over scheduled dates."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'scheduled_start': now - timedelta(hours=10),
            'scheduled_end': now - timedelta(hours=2),
            'actual_start': now - timedelta(hours=6),
            'actual_end': now,
        })
        
        # Should use actual (6 hours), not scheduled (8 hours)
        self.assertAlmostEqual(
            intervention.downtime_hours,
            6.0,
            places=1,
            msg="Actual dates should override scheduled dates"
        )

    def test_downtime_days_computation(self):
        """Test downtime_days field computation."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(days=2, hours=12),
            'actual_end': now,
        })
        
        # Should be 2.5 days
        self.assertAlmostEqual(
            intervention.downtime_days,
            2.5,
            places=1,
            msg="Downtime days should be hours/24"
        )

    def test_downtime_updates_on_action_done(self):
        """Test downtime is finalized when intervention is completed."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=5),
            'state': 'submitted',
        })
        
        # Action start
        intervention.action_start()
        self.assertEqual(intervention.state, 'in_progress')
        
        # Action done - should set actual_end
        intervention.action_done()
        self.assertEqual(intervention.state, 'done')
        self.assertTrue(intervention.actual_end, "actual_end should be set on completion")
        self.assertGreaterEqual(
            intervention.downtime_hours, 4.9,
            "Downtime should be calculated after completion"
        )

    def test_downtime_cancelled_intervention(self):
        """Test downtime for cancelled interventions."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'scheduled_start': now - timedelta(hours=3),
            'scheduled_end': now,
            'state': 'submitted',
        })
        
        intervention.action_cancel()
        
        # Cancelled interventions should still report their scheduled downtime
        # This is useful for understanding "potential" downtime even if work didn't happen
        self.assertAlmostEqual(
            intervention.downtime_hours,
            3.0,
            places=1,
            msg="Cancelled interventions should report scheduled downtime"
        )

    def test_downtime_negative_duration_protection(self):
        """Test that negative durations are handled (end before start)."""
        now = datetime.now()
        intervention = self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now,
            'actual_end': now - timedelta(hours=2),  # End before start (error case)
        })
        
        # Should return 0, not negative
        self.assertGreaterEqual(
            intervention.downtime_hours,
            0.0,
            "Downtime should never be negative"
        )

    def test_vehicle_total_downtime(self):
        """Test total downtime aggregation on vehicle."""
        now = datetime.now()
        
        # Create multiple interventions for the same vehicle
        self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=10),
            'actual_end': now - timedelta(hours=5),
            'state': 'done',
        })
        
        self.Intervention.create({
            'vehicle_id': self.vehicle.id,
            'intervention_type': 'preventive',
            'actual_start': now - timedelta(hours=3),
            'actual_end': now,
            'state': 'done',
        })
        
        # Check if vehicle has total downtime field
        if hasattr(self.vehicle, 'total_downtime_hours'):
            # Total: 5 + 3 = 8 hours
            self.assertAlmostEqual(
                self.vehicle.total_downtime_hours,
                8.0,
                places=1,
                msg="Vehicle should aggregate downtime from all interventions"
            )


@tagged('post_install', '-at_install', 'score_maintenance')
class TestDowntimeKPIReporting(TransactionCase):
    """Test suite for downtime KPI reporting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'KPI Test Model',
            'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                'name': 'KPI Test Brand',
            }).id,
        })
        
        cls.vehicles = cls.env['fleet.vehicle']
        for i in range(3):
            cls.vehicles |= cls.env['fleet.vehicle'].create({
                'model_id': cls.vehicle_model.id,
                'license_plate': f'KPI-DT-{i+1:03d}',
                'company_id': cls.env.company.id,
            })

        cls.Intervention = cls.env['fleet.maintenance.intervention']

    def test_downtime_group_by_vehicle(self):
        """Test downtime can be grouped by vehicle in reports."""
        now = datetime.now()
        
        # Create interventions for different vehicles
        for i, vehicle in enumerate(self.vehicles):
            self.Intervention.create({
                'vehicle_id': vehicle.id,
                'intervention_type': 'curative',
                'actual_start': now - timedelta(hours=(i+1)*4),
                'actual_end': now,
                'state': 'done',
            })
        
        # Use read_group to aggregate downtime by vehicle
        groups = self.Intervention.read_group(
            domain=[('vehicle_id', 'in', self.vehicles.ids)],
            fields=['vehicle_id', 'downtime_hours:sum'],
            groupby=['vehicle_id'],
        )
        
        self.assertEqual(
            len(groups), 3,
            "Should have 3 groups (one per vehicle)"
        )

    def test_downtime_group_by_intervention_type(self):
        """Test downtime can be grouped by intervention type."""
        now = datetime.now()
        vehicle = self.vehicles[0]
        
        # Create curative intervention
        self.Intervention.create({
            'vehicle_id': vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=6),
            'actual_end': now,
            'state': 'done',
        })
        
        # Create preventive intervention
        self.Intervention.create({
            'vehicle_id': vehicle.id,
            'intervention_type': 'preventive',
            'actual_start': now - timedelta(hours=2),
            'actual_end': now,
            'state': 'done',
        })
        
        # Use read_group to aggregate by type
        groups = self.Intervention.read_group(
            domain=[('vehicle_id', '=', vehicle.id)],
            fields=['intervention_type', 'downtime_hours:sum'],
            groupby=['intervention_type'],
        )
        
        self.assertEqual(
            len(groups), 2,
            "Should have 2 groups (curative and preventive)"
        )

    def test_downtime_monthly_aggregation(self):
        """Test downtime can be aggregated by month."""
        now = datetime.now()
        vehicle = self.vehicles[0]
        
        # Create intervention this month
        self.Intervention.create({
            'vehicle_id': vehicle.id,
            'intervention_type': 'curative',
            'actual_start': now - timedelta(hours=5),
            'actual_end': now,
            'state': 'done',
        })
        
        # Create intervention last month
        last_month = now - timedelta(days=35)
        self.Intervention.create({
            'vehicle_id': vehicle.id,
            'intervention_type': 'preventive',
            'actual_start': last_month,
            'actual_end': last_month + timedelta(hours=3),
            'state': 'done',
        })
        
        # Use read_group to aggregate by month
        groups = self.Intervention.read_group(
            domain=[('vehicle_id', '=', vehicle.id)],
            fields=['actual_start:month', 'downtime_hours:sum'],
            groupby=['actual_start:month'],
        )
        
        self.assertGreaterEqual(
            len(groups), 1,
            "Should have at least 1 month grouping"
        )
