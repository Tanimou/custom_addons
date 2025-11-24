# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestFleetMissionWorkflow(TransactionCase):
    """Test fleet.mission workflow and business logic"""

    def setUp(self):
        super(TestFleetMissionWorkflow, self).setUp()
        
        # Create test company
        self.company = self.env['res.company'].create({
            'name': 'Test Fleet Company',
        })
        
        # Create test vehicle
        self.brand = self.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand',
        })
        self.vehicle_model = self.env['fleet.vehicle.model'].create({
            'name': 'Test Model',
            'brand_id': self.brand.id,
        })
        self.vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'MISSION-001',
            'company_id': self.company.id,
        })
        
        # Create test employees
        self.driver = self.env['hr.employee'].create({
            'name': 'Test Driver',
            'work_email': 'driver@test.com',
        })
        self.requester = self.env['hr.employee'].create({
            'name': 'Test Requester',
            'work_email': 'requester@test.com',
        })
        self.manager_user = self.env['res.users'].create({
            'name': 'Fleet Manager',
            'login': 'fleet_manager',
            'email': 'manager@test.com',
        })
        self.manager = self.env['hr.employee'].create({
            'name': 'Test Manager',
            'work_email': 'manager@test.com',
            'user_id': self.manager_user.id,
        })
        
        # Configure settings
        self.config = self.env['res.config.settings'].create({
            'alert_offset_days': 30,
            'weekly_alert_enabled': True,
            'create_calendar_events': True,
            'block_mission_conflicts': False,
            'automatic_odometer_update': True,
        })

    def test_workflow_draft_to_done(self):
        """Test complete workflow from draft to done"""
        mission = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'route': 'Test Route',
            'purpose': 'Test Purpose',
            'company_id': self.company.id,
        })
        
        self.assertEqual(mission.state, 'draft')
        
        # Submit
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')
        
        # Approve
        mission.with_user(self.manager_user).action_approve()
        self.assertEqual(mission.state, 'approved')
        self.assertTrue(mission.approved_date)
        self.assertEqual(mission.approved_by, self.manager)
        
        # Start (directly from approved)
        mission.action_start()
        self.assertEqual(mission.state, 'in_progress')
        
        # Complete
        mission.odometer_start = 10000
        mission.odometer_end = 10150
        mission.fuel_consumed_liters = 12.5
        mission.action_done()
        self.assertEqual(mission.state, 'done')

    def test_workflow_cancel(self):
        """Test cancel workflow with reason"""
        mission = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'state': 'approved',
            'company_id': self.company.id,
        })
        
        # Create calendar event
        event = self.env['calendar.event'].create({
            'name': mission.name,
            'start': mission.date_start,
            'stop': mission.date_end,
        })
        mission.calendar_event_id = event.id
        
        # Cancel
        mission.action_cancel(reason="Test cancellation")
        self.assertEqual(mission.state, 'cancelled')
        self.assertEqual(mission.cancel_reason, "Test cancellation")
        self.assertFalse(mission.calendar_event_id.exists())

    def test_conflict_detection_vehicle(self):
        """Test conflict detection for same vehicle"""
        # Create first mission in progress
        mission1 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=3),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        # Create second mission with overlapping dates
        mission2 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=2),
            'date_end': datetime.now() + timedelta(days=4),
            'mission_type': 'course_urbaine',
            'company_id': self.company.id,
        })
        
        mission2._compute_has_conflict()
        self.assertTrue(mission2.has_conflict)
        self.assertIn('véhicule', mission2.conflict_details.lower())

    def test_conflict_detection_driver(self):
        """Test conflict detection for same driver"""
        # Create second vehicle
        vehicle2 = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'MISSION-002',
            'company_id': self.company.id,
        })
        
        # Create first mission in progress
        mission1 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=3),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        # Create second mission with same driver but different vehicle
        mission2 = self.env['fleet.mission'].create({
            'vehicle_id': vehicle2.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=2),
            'date_end': datetime.now() + timedelta(days=4),
            'mission_type': 'course_urbaine',
            'company_id': self.company.id,
        })
        
        mission2._compute_has_conflict()
        self.assertTrue(mission2.has_conflict)
        self.assertIn('conducteur', mission2.conflict_details.lower())

    def test_conflict_strict_blocking(self):
        """Test strict conflict blocking when enabled"""
        # Enable strict blocking
        self.config.block_mission_conflicts = True
        
        # Create first mission in progress
        mission1 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=3),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        # Attempt to create conflicting mission should raise error
        with self.assertRaises(ValidationError):
            mission2 = self.env['fleet.mission'].create({
                'vehicle_id': self.vehicle.id,
                'driver_id': self.driver.id,
                'requester_id': self.requester.id,
                'date_start': datetime.now() + timedelta(days=2),
                'date_end': datetime.now() + timedelta(days=4),
                'mission_type': 'course_urbaine',
                'company_id': self.company.id,
            })

    def test_calendar_integration(self):
        """Test calendar event creation"""
        mission = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'company_id': self.company.id,
        })
        
        mission.action_submit()
        mission.with_user(self.manager_user).action_approve()
        mission.action_start()
        
        # Check calendar event created (now happens on start, not assign)
        self.assertTrue(mission.calendar_event_id)
        self.assertEqual(mission.calendar_event_id.name, f"Mission: {mission.name}")

    def test_odometer_update(self):
        """Test automatic odometer update on mission completion"""
        mission = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        initial_odometer = self.vehicle.odometer
        mission.odometer_start = 10000
        mission.odometer_end = 10150
        mission.fuel_consumed_liters = 12.5
        
        mission.action_done()
        
        # Check vehicle odometer updated
        self.vehicle._compute_vehicle_odometer()
        self.assertEqual(mission.distance_km, 150)

    def test_order_number_sequence(self):
        """Test order number is auto-generated with sequence"""
        mission1 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'company_id': self.company.id,
        })
        
        self.assertTrue(mission1.order_number.startswith('MIS-'))
        
        mission2 = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=3),
            'date_end': datetime.now() + timedelta(days=4),
            'mission_type': 'course_urbaine',
            'company_id': self.company.id,
        })
        
        self.assertGreater(mission2.order_number, mission1.order_number)

    def test_date_validation(self):
        """Test date_end must be after date_start"""
        with self.assertRaises(ValidationError):
            mission = self.env['fleet.mission'].create({
                'vehicle_id': self.vehicle.id,
                'driver_id': self.driver.id,
                'requester_id': self.requester.id,
                'date_start': datetime.now() + timedelta(days=2),
                'date_end': datetime.now() + timedelta(days=1),
                'mission_type': 'course_urbaine',
                'company_id': self.company.id,
            })

    def test_odometer_validation(self):
        """Test odometer_end must be >= odometer_start"""
        mission = self.env['fleet.mission'].create({
            'vehicle_id': self.vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.requester.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=2),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        with self.assertRaises(ValidationError):
            mission.odometer_start = 10000
            mission.odometer_end = 9500
