# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T020: Tests for driver/team KPIs (FR-010)
- Count completed missions for driver
- Sum distance_km for driver
- Sum duration_days for driver
- Exclude cancelled missions
- Exclude missions without km data from km metrics
"""

from datetime import datetime, timedelta

from odoo.tests import TransactionCase


class TestVehicleDriverTeamKpis(TransactionCase):
    """Test driver/team KPI calculations from mission data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vehicle = cls.env['fleet.vehicle']
        cls.Mission = cls.env['fleet.mission']
        cls.Partner = cls.env['res.partner']
        
        # Create test vehicle model
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand KPI',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model KPI',
            'brand_id': cls.brand.id,
        })
        cls.test_vehicle = cls.Vehicle.create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-KPI-001',
        })
        
        # Create test drivers
        cls.driver_1 = cls.Partner.create({
            'name': 'Test Driver KPI 1',
            'email': 'driver1.kpi@test.com',
        })
        cls.driver_2 = cls.Partner.create({
            'name': 'Test Driver KPI 2',
            'email': 'driver2.kpi@test.com',
        })

    def _create_mission(self, driver, state='done', distance_km=0, duration_days=1, **kwargs):
        """Helper to create a mission with test defaults."""
        vals = {
            'vehicle_id': self.test_vehicle.id,
            'driver_id': driver.id,
            'name': 'Test Mission KPI',
            'date_start': datetime.now(),
            'date_end': datetime.now() + timedelta(days=duration_days),
            # Note: These fields may be computed or need different handling
            # depending on actual model implementation
        }
        vals.update(kwargs)
        mission = self.Mission.create(vals)
        
        # Set state (may need workflow methods)
        if state != 'draft':
            # This may need adjustment based on actual workflow
            mission.state = state
        
        # Set distance if model supports it
        if hasattr(mission, 'distance_km'):
            mission.distance_km = distance_km
        
        return mission

    # ==========================================================================
    # Mission Count KPI Tests
    # ==========================================================================

    def test_count_completed_missions(self):
        """KPI should count only completed (done) missions."""
        # Create missions in various states
        self._create_mission(self.driver_1, state='done')
        self._create_mission(self.driver_1, state='done')
        self._create_mission(self.driver_1, state='draft')
        self._create_mission(self.driver_1, state='cancelled')
        
        # Get KPI for driver
        completed_count = self.test_vehicle._get_driver_mission_count(self.driver_1)
        
        self.assertEqual(
            completed_count, 2,
            "Should count only completed (done) missions"
        )

    def test_count_missions_excludes_cancelled(self):
        """Cancelled missions should not be counted."""
        self._create_mission(self.driver_1, state='done')
        self._create_mission(self.driver_1, state='cancelled')
        self._create_mission(self.driver_1, state='cancelled')
        
        completed_count = self.test_vehicle._get_driver_mission_count(self.driver_1)
        
        self.assertEqual(
            completed_count, 1,
            "Cancelled missions should be excluded from count"
        )

    def test_count_missions_per_driver(self):
        """Mission counts should be specific to each driver."""
        self._create_mission(self.driver_1, state='done')
        self._create_mission(self.driver_1, state='done')
        self._create_mission(self.driver_2, state='done')
        
        count_driver_1 = self.test_vehicle._get_driver_mission_count(self.driver_1)
        count_driver_2 = self.test_vehicle._get_driver_mission_count(self.driver_2)
        
        self.assertEqual(count_driver_1, 2, "Driver 1 should have 2 missions")
        self.assertEqual(count_driver_2, 1, "Driver 2 should have 1 mission")

    # ==========================================================================
    # Distance KPI Tests
    # ==========================================================================

    def test_sum_distance_km(self):
        """KPI should sum distance_km for completed missions."""
        self._create_mission(self.driver_1, state='done', distance_km=100)
        self._create_mission(self.driver_1, state='done', distance_km=150)
        self._create_mission(self.driver_1, state='done', distance_km=200)
        
        total_km = self.test_vehicle._get_driver_total_km(self.driver_1)
        
        self.assertEqual(
            total_km, 450,
            "Should sum distance_km for all done missions"
        )

    def test_distance_excludes_cancelled(self):
        """Cancelled missions should not contribute to distance sum."""
        self._create_mission(self.driver_1, state='done', distance_km=100)
        self._create_mission(self.driver_1, state='cancelled', distance_km=500)
        
        total_km = self.test_vehicle._get_driver_total_km(self.driver_1)
        
        self.assertEqual(
            total_km, 100,
            "Cancelled mission km should be excluded"
        )

    def test_distance_excludes_zero_km(self):
        """Missions with 0 or no km should be excluded from km metrics."""
        self._create_mission(self.driver_1, state='done', distance_km=100)
        self._create_mission(self.driver_1, state='done', distance_km=0)  # No km
        self._create_mission(self.driver_1, state='done', distance_km=50)
        
        # For count with km, should be 2
        missions_with_km = self.test_vehicle._get_driver_missions_with_km_count(self.driver_1)
        
        self.assertEqual(
            missions_with_km, 2,
            "Missions with 0 km should be excluded from km-related counts"
        )

    # ==========================================================================
    # Duration KPI Tests
    # ==========================================================================

    def test_sum_duration_days(self):
        """KPI should sum duration_days for completed missions."""
        self._create_mission(self.driver_1, state='done', duration_days=2)
        self._create_mission(self.driver_1, state='done', duration_days=3)
        self._create_mission(self.driver_1, state='done', duration_days=5)
        
        total_days = self.test_vehicle._get_driver_total_days(self.driver_1)
        
        self.assertEqual(
            total_days, 10,
            "Should sum duration_days for all done missions"
        )

    def test_duration_excludes_cancelled(self):
        """Cancelled missions should not contribute to duration sum."""
        self._create_mission(self.driver_1, state='done', duration_days=5)
        self._create_mission(self.driver_1, state='cancelled', duration_days=10)
        
        total_days = self.test_vehicle._get_driver_total_days(self.driver_1)
        
        self.assertEqual(
            total_days, 5,
            "Cancelled mission days should be excluded"
        )

    # ==========================================================================
    # Average KPI Tests
    # ==========================================================================

    def test_average_distance_per_mission(self):
        """Calculate average km per mission."""
        self._create_mission(self.driver_1, state='done', distance_km=100)
        self._create_mission(self.driver_1, state='done', distance_km=200)
        self._create_mission(self.driver_1, state='done', distance_km=300)
        
        avg_km = self.test_vehicle._get_driver_avg_km(self.driver_1)
        
        self.assertEqual(
            avg_km, 200,
            "Average should be total km / mission count"
        )

    def test_average_excludes_zero_km_missions(self):
        """Average km should exclude missions with 0 km."""
        self._create_mission(self.driver_1, state='done', distance_km=100)
        self._create_mission(self.driver_1, state='done', distance_km=0)  # Excluded
        self._create_mission(self.driver_1, state='done', distance_km=200)
        
        avg_km = self.test_vehicle._get_driver_avg_km(self.driver_1)
        
        # Average should be (100 + 200) / 2 = 150, not (100 + 0 + 200) / 3
        self.assertEqual(
            avg_km, 150,
            "Average should exclude 0 km missions from both sum and count"
        )

    # ==========================================================================
    # Period Filter Tests
    # ==========================================================================

    def test_kpi_with_date_filter(self):
        """KPIs should support date period filtering."""
        now = datetime.now()
        last_month = now - timedelta(days=45)
        
        # Mission this month
        self._create_mission(
            self.driver_1, 
            state='done', 
            distance_km=100,
            date_start=now,
        )
        # Mission last month
        self._create_mission(
            self.driver_1,
            state='done',
            distance_km=500,
            date_start=last_month,
        )
        
        # Get KPI for current month only
        this_month_km = self.test_vehicle._get_driver_total_km(
            self.driver_1,
            date_from=now.replace(day=1),
            date_to=now,
        )
        
        self.assertEqual(
            this_month_km, 100,
            "KPI should filter by date period"
        )

    # ==========================================================================
    # Edge Cases
    # ==========================================================================

    def test_no_missions_returns_zero(self):
        """Driver with no missions should have 0 for all KPIs."""
        new_driver = self.Partner.create({
            'name': 'New Driver No Missions',
        })
        
        self.assertEqual(self.test_vehicle._get_driver_mission_count(new_driver), 0)
        self.assertEqual(self.test_vehicle._get_driver_total_km(new_driver), 0)
        self.assertEqual(self.test_vehicle._get_driver_total_days(new_driver), 0)

    def test_kpi_methods_exist(self):
        """Vehicle should have all KPI helper methods."""
        vehicle = self.test_vehicle
        
        required_methods = [
            '_get_driver_mission_count',
            '_get_driver_total_km',
            '_get_driver_total_days',
            '_get_driver_avg_km',
            '_get_driver_missions_with_km_count',
        ]
        
        for method in required_methods:
            self.assertTrue(
                hasattr(vehicle, method),
                f"Vehicle should have {method} method"
            )
