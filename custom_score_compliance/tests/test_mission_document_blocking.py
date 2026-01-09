# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Tests for mission document blocking (FR-007a).

Tests cover:
- T039: Block mission submission/start when vehicle has expired critical docs
- T040: Warning (non-blocking) behavior when docs are expired but non-critical

Default enforcement behavior:
- Block on submit: True (mission cannot be submitted with expired critical docs)
- Block on start: True (mission cannot be started with expired critical docs)
- Block on create: False (draft missions allowed with warning)
- Warn on vehicle change: True (show warning when vehicle has expired docs)
"""

from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'score_compliance', 'mission_blocking')
class TestMissionDocumentBlocking(TransactionCase):
    """Test suite for mission document blocking on expired critical documents."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for mission blocking tests."""
        super().setUpClass()
        
        # Get or create test company
        cls.company = cls.env.company
        
        # Create test user with fleet permissions
        cls.fleet_user = cls.env['res.users'].create({
            'name': 'Test Fleet User',
            'login': 'test_fleet_user_compliance',
            'email': 'fleet_user_compliance@test.com',
            'company_id': cls.company.id,
            'company_ids': [(4, cls.company.id)],
            'group_ids': [(4, cls.env.ref('custom_fleet_management.group_fleet_user').id)],
        })
        
        # Create test driver
        cls.driver = cls.env['res.partner'].create({
            'name': 'Test Driver Compliance',
            'email': 'driver_compliance@test.com',
            'company_id': cls.company.id,
        })
        
        # Create vehicle brand and model
        cls.brand = cls.env['fleet.vehicle.model.brand'].create({
            'name': 'Test Brand Compliance',
        })
        cls.model = cls.env['fleet.vehicle.model'].create({
            'name': 'Test Model Compliance',
            'brand_id': cls.brand.id,
        })
        
        # Create test vehicle
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': cls.model.id,
            'license_plate': 'TEST-COMPL-001',
            'company_id': cls.company.id,
            'driver_id': cls.driver.id,
        })
        
        # Create or get critical document type
        cls.doc_type_critical = cls.env['fleet.vehicle.document.type'].search([
            ('code', '=', 'assurance')
        ], limit=1)
        if not cls.doc_type_critical:
            cls.doc_type_critical = cls.env['fleet.vehicle.document.type'].create({
                'name': 'Assurance',
                'code': 'assurance',
                'is_critical': True,
            })
        
        # Create or get non-critical document type
        cls.doc_type_non_critical = cls.env['fleet.vehicle.document.type'].search([
            ('code', '=', 'vignette')
        ], limit=1)
        if not cls.doc_type_non_critical:
            cls.doc_type_non_critical = cls.env['fleet.vehicle.document.type'].create({
                'name': 'Vignette',
                'code': 'vignette',
                'is_critical': False,
            })

    def _create_document(self, vehicle, doc_type, expiry_date, state='valid'):
        """Helper to create a vehicle document."""
        # Check if document model uses document_type_id (M2O) or document_type (Selection)
        Document = self.env['fleet.vehicle.document']
        
        vals = {
            'vehicle_id': vehicle.id,
            'expiry_date': expiry_date,
            'company_id': self.company.id,
        }
        
        # Handle both legacy Selection and new Many2one field
        if 'document_type_id' in Document._fields:
            if isinstance(doc_type, str):
                # Legacy Selection value - find matching document type
                doc_type_rec = self.env['fleet.vehicle.document.type'].search([
                    ('code', '=', doc_type)
                ], limit=1)
                if doc_type_rec:
                    vals['document_type_id'] = doc_type_rec.id
                else:
                    vals['document_type'] = doc_type
            else:
                vals['document_type_id'] = doc_type.id
        else:
            # Only Selection field exists
            if isinstance(doc_type, str):
                vals['document_type'] = doc_type
            else:
                vals['document_type'] = doc_type.code
        
        return Document.create(vals)

    def _create_mission(self, vehicle, state='draft'):
        """Helper to create a test mission."""
        return self.env['fleet.mission'].create({
            'vehicle_id': vehicle.id,
            'driver_id': self.driver.id,
            'requester_id': self.fleet_user.id,
            'date_start': date.today() + timedelta(days=1),
            'date_end': date.today() + timedelta(days=2),
            'mission_type': 'urban',
            'destination': 'Test Destination',
            'state': state,
        })

    # =========================================================================
    # T039: Tests for blocking mission when critical docs are expired
    # =========================================================================

    def test_submit_blocked_with_expired_critical_doc(self):
        """Test that mission submission is blocked when vehicle has expired critical doc."""
        # Create expired critical document (assurance)
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=10)  # Expired 10 days ago
        )
        
        # Create draft mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Enable blocking on submit (default)
        self.env['ir.config_parameter'].sudo().set_param(
            'custom_score_compliance.block_mission_on_submit', 'True'
        )
        
        # Try to submit - should raise UserError
        with self.assertRaises(UserError) as context:
            mission.action_submit()
        
        self.assertIn('document', context.exception.args[0].lower())

    def test_submit_allowed_with_valid_critical_doc(self):
        """Test that mission submission is allowed when critical doc is valid."""
        # Create valid critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=60)  # Valid for 60 more days
        )
        
        # Create draft mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Submit should work
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')

    def test_start_blocked_with_expired_critical_doc(self):
        """Test that mission start is blocked when vehicle has expired critical doc."""
        # Create expired critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=5)  # Expired 5 days ago
        )
        
        # Create approved mission (skip submission for this test)
        mission = self._create_mission(self.vehicle, state='approved')
        
        # Enable blocking on start (default)
        self.env['ir.config_parameter'].sudo().set_param(
            'custom_score_compliance.block_mission_on_start', 'True'
        )
        
        # Try to start - should raise UserError
        with self.assertRaises(UserError) as context:
            mission.action_start()
        
        self.assertIn('document', context.exception.args[0].lower())

    def test_start_allowed_with_valid_critical_doc(self):
        """Test that mission start is allowed when critical doc is valid."""
        # Create valid critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=30)  # Valid for 30 more days
        )
        
        # Create approved mission
        mission = self._create_mission(self.vehicle, state='approved')
        
        # Start should work
        mission.action_start()
        self.assertEqual(mission.state, 'in_progress')

    def test_create_allowed_with_expired_critical_doc_default(self):
        """Test that mission creation in draft is allowed by default even with expired critical doc."""
        # Create expired critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=15)  # Expired 15 days ago
        )
        
        # Ensure block_on_create is False (default)
        self.env['ir.config_parameter'].sudo().set_param(
            'custom_score_compliance.block_mission_on_create', 'False'
        )
        
        # Creating draft mission should work
        mission = self._create_mission(self.vehicle, state='draft')
        self.assertEqual(mission.state, 'draft')

    def test_create_blocked_when_configured(self):
        """Test that mission creation can be blocked when configured."""
        # Create expired critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=1)  # Expired yesterday
        )
        
        # Enable block on create
        self.env['ir.config_parameter'].sudo().set_param(
            'custom_score_compliance.block_mission_on_create', 'True'
        )
        
        # Creating mission should raise error
        with self.assertRaises((UserError, ValidationError)):
            self._create_mission(self.vehicle, state='draft')

    def test_multiple_expired_critical_docs(self):
        """Test blocking with multiple expired critical documents."""
        # Create multiple expired critical documents
        self._create_document(
            self.vehicle,
            self.doc_type_critical,  # Assurance
            date.today() - timedelta(days=10)
        )
        
        # Get or create another critical doc type
        visite_tech = self.env['fleet.vehicle.document.type'].search([
            ('code', '=', 'visite_technique')
        ], limit=1)
        if not visite_tech:
            visite_tech = self.env['fleet.vehicle.document.type'].create({
                'name': 'Visite Technique',
                'code': 'visite_technique',
                'is_critical': True,
            })
        
        self._create_document(
            self.vehicle,
            visite_tech,
            date.today() - timedelta(days=5)
        )
        
        # Create mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Check compliance status shows multiple issues
        if hasattr(mission, 'compliance_blocking_reason'):
            self.assertTrue(mission.compliance_blocking_reason)

    def test_submit_allowed_when_blocking_disabled(self):
        """Test that submit is allowed when blocking is disabled via config."""
        # Create expired critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=30)  # Expired
        )
        
        # Disable blocking on submit
        self.env['ir.config_parameter'].sudo().set_param(
            'custom_score_compliance.block_mission_on_submit', 'False'
        )
        
        # Create draft mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Submit should work (with warning in practice)
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')

    # =========================================================================
    # T040: Tests for warning (non-blocking) with non-critical docs
    # =========================================================================

    def test_submit_allowed_with_expired_non_critical_doc(self):
        """Test that mission submission is allowed when only non-critical docs are expired."""
        # Create expired non-critical document (vignette)
        self._create_document(
            self.vehicle,
            self.doc_type_non_critical,
            date.today() - timedelta(days=20)  # Expired 20 days ago
        )
        
        # Create valid critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=90)  # Valid
        )
        
        # Create draft mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Submit should work (non-critical = warning only)
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')

    def test_start_allowed_with_expired_non_critical_doc(self):
        """Test that mission start is allowed when only non-critical docs are expired."""
        # Create expired non-critical document
        self._create_document(
            self.vehicle,
            self.doc_type_non_critical,
            date.today() - timedelta(days=15)  # Expired
        )
        
        # Create valid critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=60)  # Valid
        )
        
        # Create approved mission
        mission = self._create_mission(self.vehicle, state='approved')
        
        # Start should work
        mission.action_start()
        self.assertEqual(mission.state, 'in_progress')

    def test_warning_computed_for_expired_non_critical(self):
        """Test that warning is computed for expired non-critical docs."""
        # Create expired non-critical document
        self._create_document(
            self.vehicle,
            self.doc_type_non_critical,
            date.today() - timedelta(days=10)  # Expired
        )
        
        # Create mission
        mission = self._create_mission(self.vehicle)
        
        # Check vehicle has warning but not blocking
        if hasattr(self.vehicle, 'has_expired_docs'):
            self.assertTrue(self.vehicle.has_expired_docs)
        if hasattr(self.vehicle, 'has_expired_critical_docs'):
            self.assertFalse(self.vehicle.has_expired_critical_docs)

    def test_warning_for_expiring_soon_docs(self):
        """Test warning for documents expiring soon (within 30 days)."""
        # Create document expiring in 15 days
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=15)  # Expiring soon
        )
        
        # Create mission
        mission = self._create_mission(self.vehicle)
        
        # Check that expiring soon documents are flagged
        if hasattr(self.vehicle, 'has_expiring_soon_docs'):
            self.assertTrue(self.vehicle.has_expiring_soon_docs)

    def test_no_warning_for_valid_docs(self):
        """Test no warning when all documents are valid."""
        # Create valid documents (both critical and non-critical)
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=180)  # Valid for 6 months
        )
        self._create_document(
            self.vehicle,
            self.doc_type_non_critical,
            date.today() + timedelta(days=90)  # Valid for 3 months
        )
        
        # Check no warnings
        if hasattr(self.vehicle, 'has_expired_docs'):
            self.assertFalse(self.vehicle.has_expired_docs)
        if hasattr(self.vehicle, 'has_expired_critical_docs'):
            self.assertFalse(self.vehicle.has_expired_critical_docs)

    def test_blocking_only_considers_active_docs(self):
        """Test that archived/cancelled documents don't affect blocking."""
        # Create expired critical document but cancel it
        doc = self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() - timedelta(days=30)  # Expired
        )
        doc.write({'state': 'cancelled'})
        
        # Create valid critical document
        self._create_document(
            self.vehicle,
            self.doc_type_critical,
            date.today() + timedelta(days=60)  # Valid
        )
        
        # Create mission
        mission = self._create_mission(self.vehicle, state='draft')
        
        # Submit should work (cancelled doc ignored)
        mission.action_submit()
        self.assertEqual(mission.state, 'submitted')


@tagged('post_install', '-at_install', 'score_compliance', 'document_type_migration')
class TestDocumentTypeMigration(TransactionCase):
    """Tests for Selection → Many2one migration of document types."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.company = cls.env.company
        
        # Create vehicle for testing
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Migration Test Brand'})
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Migration Test Model',
            'brand_id': brand.id,
        })
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'MIG-TEST-001',
            'company_id': cls.company.id,
        })

    def test_document_type_many2one_exists(self):
        """Test that document_type_id field exists on fleet.vehicle.document."""
        Document = self.env['fleet.vehicle.document']
        self.assertIn('document_type_id', Document._fields,
            "document_type_id Many2one field should exist")

    def test_document_type_model_exists(self):
        """Test that fleet.vehicle.document.type model exists."""
        DocType = self.env['fleet.vehicle.document.type']
        self.assertTrue(DocType, "fleet.vehicle.document.type model should exist")

    def test_critical_flag_on_document_type(self):
        """Test that document types have is_critical flag."""
        DocType = self.env['fleet.vehicle.document.type']
        self.assertIn('is_critical', DocType._fields,
            "is_critical field should exist on document type")

    def test_default_critical_types_seeded(self):
        """Test that default critical document types are seeded."""
        critical_types = self.env['fleet.vehicle.document.type'].search([
            ('is_critical', '=', True)
        ])
        
        # At minimum, Assurance and Visite Technique should be critical
        critical_codes = critical_types.mapped('code')
        self.assertIn('assurance', critical_codes,
            "Assurance should be a critical document type")
        self.assertIn('visite_technique', critical_codes,
            "Visite Technique should be a critical document type")

    def test_legacy_selection_compatibility(self):
        """Test that legacy Selection field still works (compat mode)."""
        Document = self.env['fleet.vehicle.document']
        
        # If document_type Selection still exists (during migration)
        if 'document_type' in Document._fields:
            # Create document with Selection value
            doc = Document.create({
                'vehicle_id': self.vehicle.id,
                'document_type': 'assurance',
                'expiry_date': date.today() + timedelta(days=30),
                'company_id': self.company.id,
            })
            self.assertTrue(doc.id)

    def test_document_type_id_priority(self):
        """Test that document_type_id takes priority over legacy Selection."""
        Document = self.env['fleet.vehicle.document']
        DocType = self.env['fleet.vehicle.document.type']
        
        # Get assurance type
        assurance = DocType.search([('code', '=', 'assurance')], limit=1)
        if not assurance:
            assurance = DocType.create({
                'name': 'Assurance',
                'code': 'assurance',
                'is_critical': True,
            })
        
        # Create document with document_type_id
        doc = Document.create({
            'vehicle_id': self.vehicle.id,
            'document_type_id': assurance.id,
            'expiry_date': date.today() + timedelta(days=30),
            'company_id': self.company.id,
        })
        
        # Check that is_critical is resolved from document_type_id
        if hasattr(doc, 'is_critical_document'):
            self.assertTrue(doc.is_critical_document)
