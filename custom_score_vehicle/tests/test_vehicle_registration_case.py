# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T016: Tests for vehicle registration case workflow (FR-008)
- States: in_progress → validated OR rejected
- Rejection requires rejection_reason (constraint)
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestVehicleRegistrationCase(TransactionCase):
    """Test registration case workflow and rejection reason constraint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RegistrationCase = cls.env['fleet.vehicle.registration.case']
        cls.Vehicle = cls.env['fleet.vehicle']
        
        # Create test vehicle
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Registration',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Registration',
            'brand_id': cls.brand.id,
        })
        cls.test_vehicle = cls.Vehicle.create({
            'model_id': cls.vehicle_model.id,
            'license_plate': 'TEST-REG-001',
        })

    def _create_registration_case(self, **kwargs):
        """Helper to create a registration case with test defaults."""
        vals = {
            'vehicle_id': self.test_vehicle.id,
            'name': 'Test Registration Case',
        }
        vals.update(kwargs)
        return self.RegistrationCase.create(vals)

    # ==========================================================================
    # State Workflow Tests
    # ==========================================================================

    def test_default_state_in_progress(self):
        """New registration case should start in 'in_progress' state."""
        case = self._create_registration_case()
        self.assertEqual(case.state, 'in_progress', "Default state should be 'in_progress'")

    def test_transition_to_validated(self):
        """Registration case can transition from in_progress to validated."""
        case = self._create_registration_case()
        case.action_validate()
        self.assertEqual(case.state, 'validated', "State should be 'validated' after validation")

    def test_transition_to_rejected(self):
        """Registration case can transition from in_progress to rejected (with reason)."""
        case = self._create_registration_case()
        case.write({'rejection_reason': 'Missing required documents'})
        case.action_reject()
        self.assertEqual(case.state, 'rejected', "State should be 'rejected' after rejection")

    def test_validated_is_final(self):
        """Validated state should be final (cannot change back)."""
        case = self._create_registration_case()
        case.action_validate()
        with self.assertRaises((ValidationError, UserError)):
            case.action_reject()

    def test_rejected_is_final(self):
        """Rejected state should be final (cannot change back)."""
        case = self._create_registration_case()
        case.write({'rejection_reason': 'Invalid VIN'})
        case.action_reject()
        with self.assertRaises((ValidationError, UserError)):
            case.action_validate()

    # ==========================================================================
    # Rejection Reason Constraint Tests
    # ==========================================================================

    def test_reject_without_reason_fails(self):
        """Rejecting without rejection_reason should raise ValidationError."""
        case = self._create_registration_case()
        # Do not set rejection_reason
        with self.assertRaises(ValidationError):
            case.action_reject()

    def test_reject_with_empty_reason_fails(self):
        """Rejecting with empty rejection_reason should raise ValidationError."""
        case = self._create_registration_case()
        case.write({'rejection_reason': ''})
        with self.assertRaises(ValidationError):
            case.action_reject()

    def test_reject_with_reason_succeeds(self):
        """Rejecting with valid rejection_reason should succeed."""
        case = self._create_registration_case()
        case.write({'rejection_reason': 'Documents are not compliant'})
        case.action_reject()
        self.assertEqual(case.state, 'rejected')
        self.assertEqual(case.rejection_reason, 'Documents are not compliant')

    # ==========================================================================
    # Vehicle Link Tests
    # ==========================================================================

    def test_registration_case_linked_to_vehicle(self):
        """Registration case should be linked to a vehicle."""
        case = self._create_registration_case()
        self.assertEqual(case.vehicle_id, self.test_vehicle)

    def test_vehicle_has_registration_cases(self):
        """Vehicle should have One2many to registration cases."""
        case1 = self._create_registration_case(name='Case 1')
        case2 = self._create_registration_case(name='Case 2')
        # Check vehicle can access its registration cases
        self.assertIn(case1, self.test_vehicle.registration_case_ids)
        self.assertIn(case2, self.test_vehicle.registration_case_ids)

    # ==========================================================================
    # Chatter/History Tests
    # ==========================================================================

    def test_registration_case_has_chatter(self):
        """Registration case should have chatter (inherit mail.thread)."""
        case = self._create_registration_case()
        # Post a message - if model inherits mail.thread this should work
        case.message_post(body="Test message")
        self.assertTrue(
            case.message_ids.filtered(lambda m: 'Test message' in (m.body or '')),
            "Message should be posted in chatter"
        )

    def test_state_change_tracked(self):
        """State changes should be tracked in chatter."""
        case = self._create_registration_case()
        initial_messages = len(case.message_ids)
        case.action_validate()
        # State change should produce a tracking message
        self.assertGreater(
            len(case.message_ids), initial_messages,
            "State change should add a tracking message"
        )
