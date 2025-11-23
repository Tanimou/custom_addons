# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestFleetVehicle(TransactionCase):
    """Test fleet.vehicle model extensions and computed fields"""

    def setUp(self):
        super(TestFleetVehicle, self).setUp()
        
        # Create test company
        self.company = self.env['res.company'].create({
            'name': 'Test Fleet Company',
        })
        
        # Create test vehicle model
        self.brand = self.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand',
        })
        self.vehicle_model = self.env['fleet.vehicle.model'].create({
            'name': 'Test Model',
            'brand_id': self.brand.id,
        })
        
        # Create test document types
        self.doc_type_assurance = self.env['fleet.vehicle.document.type'].create({
            'name': 'Assurance Test',
            'code': 'assurance',
            'is_critical': True,
        })
        self.doc_type_visite = self.env['fleet.vehicle.document.type'].create({
            'name': 'Visite Technique Test',
            'code': 'visite_technique',
            'is_critical': True,
        })
        
        # Create test employee (driver)
        self.driver = self.env['hr.employee'].create({
            'name': 'Test Driver',
            'work_email': 'driver@test.com',
        })

    def test_vehicle_code_sequence(self):
        """Test that vehicle code is auto-generated with sequence"""
        vehicle1 = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-001',
            'company_id': self.company.id,
        })
        self.assertTrue(vehicle1.vehicle_code.startswith('VEH-'))
        self.assertEqual(len(vehicle1.vehicle_code), 8)  # VEH-0001
        
        vehicle2 = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-002',
            'company_id': self.company.id,
        })
        # Second vehicle should have incremented code
        self.assertGreater(vehicle2.vehicle_code, vehicle1.vehicle_code)

    def test_administrative_state_ok(self):
        """Test administrative state is 'ok' when all documents are valid"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-OK',
            'company_id': self.company.id,
        })
        
        # Create document expiring in 60 days (> 30 days threshold)
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_assurance.id,
            'expiry_date': datetime.now().date() + timedelta(days=60),
            'company_id': self.company.id,
        })
        
        vehicle._compute_administrative_state()
        self.assertEqual(vehicle.administrative_state, 'ok')

    def test_administrative_state_warning(self):
        """Test administrative state is 'warning' when document expires soon"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-WARN',
            'company_id': self.company.id,
        })
        
        # Create document expiring in 15 days (< 30 days threshold)
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_visite.id,
            'expiry_date': datetime.now().date() + timedelta(days=15),
            'company_id': self.company.id,
        })
        
        vehicle._compute_administrative_state()
        self.assertEqual(vehicle.administrative_state, 'warning')

    def test_administrative_state_critical(self):
        """Test administrative state is 'critical' when document is expired"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-CRIT',
            'company_id': self.company.id,
        })
        
        # Create expired document
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_assurance.id,
            'expiry_date': datetime.now().date() - timedelta(days=5),
            'company_id': self.company.id,
        })
        
        vehicle._compute_administrative_state()
        self.assertEqual(vehicle.administrative_state, 'critical')

    def test_is_available_true(self):
        """Test vehicle is available when no active missions"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-AVAIL',
            'company_id': self.company.id,
        })
        
        vehicle._compute_is_available()
        self.assertTrue(vehicle.is_available)

    def test_is_available_false(self):
        """Test vehicle is not available when mission in progress"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-BUSY',
            'company_id': self.company.id,
        })
        
        # Create mission in progress
        self.env['fleet.mission'].create({
            'vehicle_id': vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.driver.id,
            'date_start': datetime.now(),
            'date_end': datetime.now() + timedelta(days=1),
            'mission_type': 'course_urbaine',
            'state': 'in_progress',
            'company_id': self.company.id,
        })
        
        vehicle._compute_is_available()
        self.assertFalse(vehicle.is_available)

    def test_action_view_missions(self):
        """Test action_view_missions returns correct action dict"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-ACT',
            'company_id': self.company.id,
        })
        
        action = vehicle.action_view_missions()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'fleet.mission')
        self.assertIn('domain', action)
        self.assertIn(('vehicle_id', '=', vehicle.id), action['domain'])

    def test_action_view_documents(self):
        """Test action_view_documents returns correct action dict"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-DOC',
            'company_id': self.company.id,
        })
        
        action = vehicle.action_view_documents()
        
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'fleet.vehicle.document')
        self.assertIn('domain', action)
        self.assertIn(('vehicle_id', '=', vehicle.id), action['domain'])

    def test_next_expiry_date_compute(self):
        """Test next_expiry_date is computed correctly"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-EXPIRY',
            'company_id': self.company.id,
        })
        
        expiry_date = datetime.now().date() + timedelta(days=20)
        
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_assurance.id,
            'expiry_date': expiry_date,
            'company_id': self.company.id,
        })
        
        vehicle._compute_next_expiry_date()
        self.assertEqual(vehicle.next_expiry_date, expiry_date)

    def test_days_until_next_expiry_compute(self):
        """Test days_until_next_expiry is computed correctly"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-DAYS',
            'company_id': self.company.id,
        })
        
        expiry_date = datetime.now().date() + timedelta(days=25)
        
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_assurance.id,
            'expiry_date': expiry_date,
            'company_id': self.company.id,
        })
        
        vehicle._compute_days_until_next_expiry()
        self.assertEqual(vehicle.days_until_next_expiry, 25)

    def test_action_send_weekly_digest(self):
        """Test weekly digest email action"""
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.vehicle_model.id,
            'license_plate': 'TEST-DIGEST',
            'company_id': self.company.id,
        })
        
        # Create expiring document
        self.env['fleet.vehicle.document'].create({
            'vehicle_id': vehicle.id,
            'document_type_id': self.doc_type_assurance.id,
            'expiry_date': datetime.now().date() + timedelta(days=20),
            'company_id': self.company.id,
        })
        
        # Should not raise exception
        result = vehicle.action_send_weekly_digest()
        self.assertTrue(result)
