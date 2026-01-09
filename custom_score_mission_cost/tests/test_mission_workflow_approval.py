# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for mission workflow states and approval traceability.
FR-013a: Workflow states (Brouillon → À approuver → Approuvé → En cours → Terminé/Annulé)
FR-013b: "Cannot start unless approved" enforcement
FR-013c: Approval traceability (user + datetime)
"""

from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestMissionWorkflowApproval(TransactionCase):
    """Test suite for mission workflow and approval traceability (FR-013a/b/c)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Get existing fleet manager user or create one
        cls.fleet_manager_group = cls.env.ref('custom_fleet_management.group_fleet_manager', raise_if_not_found=False)
        if not cls.fleet_manager_group:
            cls.fleet_manager_group = cls.env['res.groups'].create({
                'name': 'Fleet Manager (Test)',
                'category_id': cls.env.ref('base.module_category_services_fleet', raise_if_not_found=False).id or False,
            })
        
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Fleet Manager Test',
            'login': 'fleet_manager_test_score',
            'email': 'fleet.manager@test.score',
            'group_ids': [(4, cls.fleet_manager_group.id)],
        })
        
        cls.user_regular = cls.env['res.users'].create({
            'name': 'Regular User Test',
            'login': 'regular_user_test_score',
            'email': 'regular@test.score',
        })
        
        # Create a partner (driver)
        cls.driver = cls.env['res.partner'].create({
            'name': 'Test Driver',
            'email': 'driver@test.score',
        })
        
        # Create a vehicle
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand SCORE',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model SCORE',
            'brand_id': cls.brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'name': 'Test Vehicle SCORE',
            'model_id': cls.model.id,
            'license_plate': 'TEST-SCORE-01',
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
            'mission_type': 'urban',
        }
        vals.update(kwargs)
        return self.env['fleet.mission'].create(vals)

    # ========== FR-013a: Workflow States ==========

    def test_mission_initial_state_is_draft(self):
        """Mission should start in 'draft' state."""
        mission = self._create_mission()
        self.assertEqual(mission.state, 'draft')

    def test_mission_submit_from_draft(self):
        """Mission can be submitted from draft state."""
        mission = self._create_mission()
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')

    def test_mission_approve_from_submitted(self):
        """Mission can be approved from submitted state."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        self.assertEqual(mission.state, 'approved')

    def test_mission_start_from_approved(self):
        """Mission can be started from approved state (with odo_start)."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.write({'odo_start': 10000.0})
        mission.action_start()
        self.assertEqual(mission.state, 'in_progress')

    def test_mission_complete_from_in_progress(self):
        """Mission can be completed from in_progress state (with odo_end)."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.write({'odo_start': 10000.0})
        mission.action_start()
        mission.write({'odo_end': 10500.0})
        mission.action_done()
        self.assertEqual(mission.state, 'done')

    def test_mission_cancel_from_any_except_done(self):
        """Mission can be cancelled from draft, submitted, approved, or in_progress."""
        # Cancel from draft
        mission1 = self._create_mission()
        mission1.action_cancel()
        self.assertEqual(mission1.state, 'cancelled')
        
        # Cancel from submitted
        mission2 = self._create_mission()
        mission2.action_submit()
        mission2.action_cancel()
        self.assertEqual(mission2.state, 'cancelled')
        
        # Cancel from approved
        mission3 = self._create_mission()
        mission3.action_submit()
        mission3.with_user(self.user_manager).action_approve()
        mission3.action_cancel()
        self.assertEqual(mission3.state, 'cancelled')
        
        # Cancel from in_progress
        mission4 = self._create_mission()
        mission4.action_submit()
        mission4.with_user(self.user_manager).action_approve()
        mission4.write({'odo_start': 10000.0})
        mission4.action_start()
        mission4.action_cancel()
        self.assertEqual(mission4.state, 'cancelled')

    def test_mission_cannot_cancel_done(self):
        """Mission cannot be cancelled once completed."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.write({'odo_start': 10000.0})
        mission.action_start()
        mission.write({'odo_end': 10500.0})
        mission.action_done()
        
        with self.assertRaises(UserError):
            mission.action_cancel()

    # ========== FR-013b: Cannot Start Unless Approved ==========

    def test_mission_cannot_start_from_draft(self):
        """Mission cannot be started directly from draft state."""
        mission = self._create_mission()
        mission.write({'odo_start': 10000.0})
        with self.assertRaises(UserError):
            mission.action_start()

    def test_mission_cannot_start_from_submitted(self):
        """Mission cannot be started from submitted state (must be approved first)."""
        mission = self._create_mission()
        mission.action_submit()
        mission.write({'odo_start': 10000.0})
        with self.assertRaises(UserError):
            mission.action_start()

    def test_mission_cannot_start_without_odometer(self):
        """Mission cannot be started without odo_start value."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        
        with self.assertRaises(UserError):
            mission.action_start()

    # ========== FR-013c: Approval Traceability ==========

    def test_approval_records_user_and_datetime(self):
        """Approval must record the approving user and datetime."""
        mission = self._create_mission()
        mission.action_submit()
        
        before_approval = datetime.now()
        mission.with_user(self.user_manager).action_approve()
        after_approval = datetime.now()
        
        # Check approver
        self.assertEqual(mission.approved_by, self.user_manager)
        
        # Check approval date is set and reasonable
        self.assertIsNotNone(mission.approval_date)
        self.assertGreaterEqual(mission.approval_date, before_approval)
        self.assertLessEqual(mission.approval_date, after_approval + timedelta(seconds=2))

    def test_approval_generates_order_number(self):
        """Approval should generate an order number (if not already set)."""
        mission = self._create_mission()
        self.assertFalse(mission.order_number)
        
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        
        self.assertTrue(mission.order_number)
        self.assertTrue(mission.order_number.startswith('OMI-'))

    def test_reset_clears_approval_fields(self):
        """Resetting to draft should clear approval fields."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.action_cancel()
        mission.action_reset_to_draft()
        
        self.assertEqual(mission.state, 'draft')
        self.assertFalse(mission.approved_by)
        self.assertFalse(mission.approval_date)

    # ========== Transition Validation Tests ==========

    def test_cannot_submit_without_destination(self):
        """Mission cannot be submitted without destination."""
        mission = self._create_mission(destination=False)
        with self.assertRaises(UserError):
            mission.action_submit()

    def test_cannot_submit_without_objective(self):
        """Mission cannot be submitted without objective."""
        mission = self._create_mission(objective=False)
        with self.assertRaises(UserError):
            mission.action_submit()

    def test_cannot_approve_from_draft(self):
        """Mission cannot be approved directly from draft (must be submitted first)."""
        mission = self._create_mission()
        with self.assertRaises(UserError):
            mission.with_user(self.user_manager).action_approve()

    def test_cannot_complete_without_odo_end(self):
        """Mission cannot be completed without odo_end value."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.write({'odo_start': 10000.0})
        mission.action_start()
        
        with self.assertRaises(UserError):
            mission.action_done()

    def test_odo_end_must_be_greater_than_odo_start(self):
        """odo_end must be greater than odo_start when completing."""
        mission = self._create_mission()
        mission.action_submit()
        mission.with_user(self.user_manager).action_approve()
        mission.write({'odo_start': 10000.0})
        mission.action_start()
        mission.write({'odo_end': 9000.0})  # Less than start
        
        with self.assertRaises(ValidationError):
            mission.action_done()
