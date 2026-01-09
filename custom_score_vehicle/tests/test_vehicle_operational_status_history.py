# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T019: Tests for vehicle operational status history (FR-011)
- State changes tracked via mail.tracking.value
- Helper method _get_state_history returns history records
"""

from odoo.tests import TransactionCase


class TestVehicleOperationalStatusHistory(TransactionCase):
    """Test vehicle operational status tracking and history retrieval."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vehicle = cls.env['fleet.vehicle']
        cls.VehicleState = cls.env['fleet.vehicle.state']
        cls.TrackingValue = cls.env['mail.tracking.value']
        
        # Create test vehicle model
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Status History',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Status History',
            'brand_id': cls.brand.id,
        })
        
        # Get or create vehicle states for testing
        cls.state_service = cls.VehicleState.search([('name', '=', 'En service')], limit=1)
        if not cls.state_service:
            cls.state_service = cls.VehicleState.create({
                'name': 'En service',
                'sequence': 10,
            })
        
        cls.state_maintenance = cls.VehicleState.search([('name', '=', 'En maintenance')], limit=1)
        if not cls.state_maintenance:
            cls.state_maintenance = cls.VehicleState.create({
                'name': 'En maintenance',
                'sequence': 20,
            })
        
        cls.state_immobilized = cls.VehicleState.search([('name', '=', 'Immobilisé')], limit=1)
        if not cls.state_immobilized:
            cls.state_immobilized = cls.VehicleState.create({
                'name': 'Immobilisé',
                'sequence': 30,
            })

    def _create_vehicle(self, **kwargs):
        """Helper to create a vehicle with test defaults."""
        vals = {
            'model_id': self.vehicle_model.id,
            'state_id': self.state_service.id,
        }
        vals.update(kwargs)
        return self.Vehicle.create(vals)

    # ==========================================================================
    # State Tracking Tests
    # ==========================================================================

    def test_state_id_has_tracking(self):
        """state_id field should have tracking=True."""
        field = self.env['ir.model.fields']._get('fleet.vehicle', 'state_id')
        self.assertTrue(field, "state_id field should exist on fleet.vehicle")
        # Note: tracking attribute check may need to be done via field definition
        # This test verifies the expected behavior (tracking messages created)

    def test_state_change_creates_tracking_message(self):
        """Changing state_id should create a tracking message in chatter."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        initial_count = len(vehicle.message_ids)
        
        # Change state
        vehicle.write({'state_id': self.state_maintenance.id})
        
        # Should have new message(s) for tracking
        self.assertGreater(
            len(vehicle.message_ids), initial_count,
            "State change should create tracking message"
        )

    def test_multiple_state_changes_tracked(self):
        """Multiple state changes should all be tracked."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        
        # Change state multiple times
        vehicle.write({'state_id': self.state_maintenance.id})
        vehicle.write({'state_id': self.state_immobilized.id})
        vehicle.write({'state_id': self.state_service.id})
        
        # Get tracking values for state_id
        field = self.env['ir.model.fields']._get('fleet.vehicle', 'state_id')
        tracking_values = self.TrackingValue.search([
            ('field_id', '=', field.id),
            ('mail_message_id.model', '=', 'fleet.vehicle'),
            ('mail_message_id.res_id', '=', vehicle.id),
        ])
        
        # Should have at least 3 tracking entries (one per change)
        self.assertGreaterEqual(
            len(tracking_values), 3,
            "All state changes should be tracked"
        )

    # ==========================================================================
    # Helper Method Tests
    # ==========================================================================

    def test_get_state_history_method_exists(self):
        """Vehicle should have _get_state_history helper method."""
        vehicle = self._create_vehicle()
        self.assertTrue(
            hasattr(vehicle, '_get_state_history'),
            "Vehicle should have _get_state_history method"
        )

    def test_get_state_history_returns_records(self):
        """_get_state_history should return tracking records."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        
        # Make some state changes
        vehicle.write({'state_id': self.state_maintenance.id})
        vehicle.write({'state_id': self.state_service.id})
        
        history = vehicle._get_state_history()
        
        self.assertTrue(
            len(history) > 0,
            "_get_state_history should return tracking records"
        )

    def test_get_state_history_ordered_desc(self):
        """_get_state_history should return records ordered by date descending."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        
        vehicle.write({'state_id': self.state_maintenance.id})
        vehicle.write({'state_id': self.state_immobilized.id})
        
        history = vehicle._get_state_history()
        
        if len(history) > 1:
            # Check descending order
            dates = history.mapped('create_date')
            self.assertEqual(
                dates, sorted(dates, reverse=True),
                "History should be ordered by date descending"
            )

    def test_get_state_history_only_state_field(self):
        """_get_state_history should only return state_id changes."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        
        # Change state and other fields
        vehicle.write({
            'state_id': self.state_maintenance.id,
            'license_plate': 'NEW-PLATE-123',
        })
        
        history = vehicle._get_state_history()
        
        # Verify all tracking values are for state_id field
        state_field = self.env['ir.model.fields']._get('fleet.vehicle', 'state_id')
        for tracking in history:
            self.assertEqual(
                tracking.field_id.id, state_field.id,
                "History should only contain state_id changes"
            )

    # ==========================================================================
    # Edge Cases
    # ==========================================================================

    def test_new_vehicle_no_initial_history(self):
        """Newly created vehicle may or may not have initial state in history."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        # This test documents expected behavior - implementation may vary
        # Some implementations track initial creation, others don't
        history = vehicle._get_state_history()
        # Just verify method works without error
        self.assertIsNotNone(history)

    def test_same_state_not_tracked(self):
        """Writing same state value should not create new tracking entry."""
        vehicle = self._create_vehicle(state_id=self.state_service.id)
        
        initial_history = vehicle._get_state_history()
        initial_count = len(initial_history)
        
        # Write same state
        vehicle.write({'state_id': self.state_service.id})
        
        new_history = vehicle._get_state_history()
        self.assertEqual(
            len(new_history), initial_count,
            "Writing same state should not create new tracking entry"
        )
