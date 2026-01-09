# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T015: Tests for conditional uniqueness on fleet.vehicle (FR-004)
- VIN (vin_sn) must be unique ONLY IF set
- License plate (license_plate) must be unique ONLY IF set
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestVehicleUniqueness(TransactionCase):
    """Test conditional uniqueness constraints on vehicle VIN and license plate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vehicle = cls.env['fleet.vehicle']
        # Get or create a vehicle model for tests
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Uniqueness',
        })
        cls.vehicle_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Uniqueness',
            'brand_id': cls.brand.id,
        })

    def _create_vehicle(self, **kwargs):
        """Helper to create a vehicle with test defaults."""
        vals = {
            'model_id': self.vehicle_model.id,
            'license_plate': False,
            'vin_sn': False,
        }
        vals.update(kwargs)
        return self.Vehicle.create(vals)

    # ==========================================================================
    # VIN Uniqueness Tests
    # ==========================================================================

    def test_vin_unique_when_both_set(self):
        """Two vehicles with same non-empty VIN should raise ValidationError."""
        self._create_vehicle(vin_sn='VIN123456789ABCDE')
        with self.assertRaises(ValidationError):
            self._create_vehicle(vin_sn='VIN123456789ABCDE')

    def test_vin_empty_allows_duplicates(self):
        """Two vehicles with empty/False VIN should be allowed."""
        v1 = self._create_vehicle(vin_sn=False)
        v2 = self._create_vehicle(vin_sn=False)
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_vin_one_empty_one_set(self):
        """One vehicle with VIN, one without - should be allowed."""
        v1 = self._create_vehicle(vin_sn='VINUNIQUE12345678')
        v2 = self._create_vehicle(vin_sn=False)
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_vin_different_values(self):
        """Two vehicles with different VINs should be allowed."""
        v1 = self._create_vehicle(vin_sn='VINAAAAAAAAA11111')
        v2 = self._create_vehicle(vin_sn='VINBBBBBBBBB22222')
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_vin_update_to_duplicate(self):
        """Updating VIN to match existing vehicle should raise ValidationError."""
        v1 = self._create_vehicle(vin_sn='VINEXISTING123456')
        v2 = self._create_vehicle(vin_sn='VINDIFFERENT78901')
        with self.assertRaises(ValidationError):
            v2.write({'vin_sn': 'VINEXISTING123456'})

    # ==========================================================================
    # License Plate Uniqueness Tests
    # ==========================================================================

    def test_plate_unique_when_both_set(self):
        """Two vehicles with same non-empty plate should raise ValidationError."""
        self._create_vehicle(license_plate='AB-123-CD')
        with self.assertRaises(ValidationError):
            self._create_vehicle(license_plate='AB-123-CD')

    def test_plate_empty_allows_duplicates(self):
        """Two vehicles with empty/False plate should be allowed."""
        v1 = self._create_vehicle(license_plate=False)
        v2 = self._create_vehicle(license_plate=False)
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_plate_one_empty_one_set(self):
        """One vehicle with plate, one without - should be allowed."""
        v1 = self._create_vehicle(license_plate='XY-999-ZZ')
        v2 = self._create_vehicle(license_plate=False)
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_plate_different_values(self):
        """Two vehicles with different plates should be allowed."""
        v1 = self._create_vehicle(license_plate='AA-111-AA')
        v2 = self._create_vehicle(license_plate='BB-222-BB')
        self.assertTrue(v1.id and v2.id, "Both vehicles should be created without error")

    def test_plate_update_to_duplicate(self):
        """Updating plate to match existing vehicle should raise ValidationError."""
        v1 = self._create_vehicle(license_plate='CC-333-CC')
        v2 = self._create_vehicle(license_plate='DD-444-DD')
        with self.assertRaises(ValidationError):
            v2.write({'license_plate': 'CC-333-CC'})

    # ==========================================================================
    # Combined Tests
    # ==========================================================================

    def test_both_vin_and_plate_unique(self):
        """Vehicle with both VIN and plate set - both must be unique."""
        self._create_vehicle(vin_sn='VINCOMBO12345678A', license_plate='EE-555-EE')
        # Same VIN, different plate - should fail
        with self.assertRaises(ValidationError):
            self._create_vehicle(vin_sn='VINCOMBO12345678A', license_plate='FF-666-FF')
        # Different VIN, same plate - should fail
        with self.assertRaises(ValidationError):
            self._create_vehicle(vin_sn='VINCOMBO87654321B', license_plate='EE-555-EE')
