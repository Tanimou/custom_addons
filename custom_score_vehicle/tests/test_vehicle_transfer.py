# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T017: Tests for vehicle transfer workflow (FR-016)
- States: draft → confirmed → validated → delivered (or cancelled)
- Validation required before delivery
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestVehicleTransfer(TransactionCase):
    """Test vehicle transfer workflow and validation requirements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transfer = cls.env['fleet.vehicle.transfer']
        cls.Vehicle = cls.env['fleet.vehicle']
        cls.Location = cls.env['stock.location']
        
        # Create test vehicle
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Transfer',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Transfer',
            'brand_id': cls.brand.id,
        })
        cls.test_vehicle = cls.Vehicle.create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-TRF-001',
        })
        
        # Create test locations (internal stock locations)
        cls.location_src = cls.Location.create({
            'name': 'Source Location Transfer Test',
            'usage': 'internal',
        })
        cls.location_dest = cls.Location.create({
            'name': 'Destination Location Transfer Test',
            'usage': 'internal',
        })

    def _create_transfer(self, **kwargs):
        """Helper to create a transfer with test defaults."""
        vals = {
            'vehicle_id': self.test_vehicle.id,
            'location_src_id': self.location_src.id,
            'location_dest_id': self.location_dest.id,
            'name': 'Test Transfer',
        }
        vals.update(kwargs)
        return self.Transfer.create(vals)

    # ==========================================================================
    # State Workflow Tests
    # ==========================================================================

    def test_default_state_draft(self):
        """New transfer should start in 'draft' state."""
        transfer = self._create_transfer()
        self.assertEqual(transfer.state, 'draft', "Default state should be 'draft'")

    def test_transition_draft_to_confirmed(self):
        """Transfer can transition from draft to confirmed."""
        transfer = self._create_transfer()
        transfer.action_confirm()
        self.assertEqual(transfer.state, 'confirmed', "State should be 'confirmed'")

    def test_transition_confirmed_to_validated(self):
        """Transfer can transition from confirmed to validated."""
        transfer = self._create_transfer()
        transfer.action_confirm()
        transfer.action_validate()
        self.assertEqual(transfer.state, 'validated', "State should be 'validated'")

    def test_transition_validated_to_delivered(self):
        """Transfer can transition from validated to delivered."""
        transfer = self._create_transfer()
        transfer.action_confirm()
        transfer.action_validate()
        transfer.action_deliver()
        self.assertEqual(transfer.state, 'delivered', "State should be 'delivered'")

    def test_transition_to_cancelled(self):
        """Transfer can be cancelled from draft/confirmed states."""
        transfer = self._create_transfer()
        transfer.action_cancel()
        self.assertEqual(transfer.state, 'cancelled', "State should be 'cancelled'")

    # ==========================================================================
    # Validation Before Delivery Tests
    # ==========================================================================

    def test_cannot_deliver_without_validation(self):
        """Cannot deliver a transfer that hasn't been validated."""
        transfer = self._create_transfer()
        transfer.action_confirm()
        # State is 'confirmed' - should not allow delivery
        with self.assertRaises((ValidationError, UserError)):
            transfer.action_deliver()

    def test_cannot_deliver_from_draft(self):
        """Cannot deliver a transfer directly from draft."""
        transfer = self._create_transfer()
        with self.assertRaises((ValidationError, UserError)):
            transfer.action_deliver()

    def test_can_deliver_after_validation(self):
        """Can deliver a transfer after proper validation flow."""
        transfer = self._create_transfer()
        transfer.action_confirm()
        transfer.action_validate()
        # Now delivery should work
        transfer.action_deliver()
        self.assertEqual(transfer.state, 'delivered')

    # ==========================================================================
    # Vehicle Location Tracking Tests
    # ==========================================================================

    def test_delivery_updates_vehicle_location(self):
        """Completing a transfer should update vehicle's current_location_id."""
        # Set initial location
        self.test_vehicle.current_location_id = self.location_src.id
        
        transfer = self._create_transfer()
        transfer.action_confirm()
        transfer.action_validate()
        transfer.action_deliver()
        
        # Vehicle location should now be destination
        self.assertEqual(
            self.test_vehicle.current_location_id, self.location_dest,
            "Vehicle current_location_id should be updated to destination"
        )

    def test_cancelled_transfer_no_location_update(self):
        """Cancelled transfer should not update vehicle location."""
        self.test_vehicle.current_location_id = self.location_src.id
        
        transfer = self._create_transfer()
        transfer.action_confirm()
        transfer.action_cancel()
        
        # Vehicle location should remain unchanged
        self.assertEqual(
            self.test_vehicle.current_location_id, self.location_src,
            "Cancelled transfer should not change vehicle location"
        )

    # ==========================================================================
    # Required Fields Tests
    # ==========================================================================

    def test_transfer_requires_vehicle(self):
        """Transfer creation requires vehicle_id."""
        with self.assertRaises(Exception):
            self.Transfer.create({
                'location_src_id': self.location_src.id,
                'location_dest_id': self.location_dest.id,
                'name': 'Invalid Transfer',
            })

    def test_transfer_requires_locations(self):
        """Transfer creation requires both source and destination locations."""
        # Missing destination
        with self.assertRaises(Exception):
            self.Transfer.create({
                'vehicle_id': self.test_vehicle.id,
                'location_src_id': self.location_src.id,
                'name': 'Invalid Transfer',
            })

    def test_transfer_different_locations(self):
        """Source and destination locations must be different."""
        with self.assertRaises(ValidationError):
            self._create_transfer(
                location_src_id=self.location_src.id,
                location_dest_id=self.location_src.id,  # Same as source
            )

    # ==========================================================================
    # Chatter/History Tests
    # ==========================================================================

    def test_transfer_has_chatter(self):
        """Transfer should have chatter (inherit mail.thread)."""
        transfer = self._create_transfer()
        transfer.message_post(body="Test transfer message")
        self.assertTrue(
            transfer.message_ids.filtered(lambda m: 'Test transfer message' in (m.body or '')),
            "Message should be posted in chatter"
        )

    def test_state_change_tracked(self):
        """State changes should be tracked in chatter."""
        transfer = self._create_transfer()
        initial_messages = len(transfer.message_ids)
        transfer.action_confirm()
        self.assertGreater(
            len(transfer.message_ids), initial_messages,
            "State change should add a tracking message"
        )
