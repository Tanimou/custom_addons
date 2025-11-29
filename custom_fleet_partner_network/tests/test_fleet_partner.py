# -*- coding: utf-8 -*-
"""Tests pour les profils partenaires Fleet."""

from odoo.exceptions import ValidationError
from odoo.tests import SavepointCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFleetPartnerProfileUnit(SavepointCase):
    """Tests unitaires centrés sur le modèle fleet.partner.profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile_model = cls.env['fleet.partner.profile']
        cls.partner_model = cls.env['res.partner']
        cls.partner = cls.partner_model.create({
            'name': 'Assistance Hexagone',
            'is_company': True,
            'email': 'support@example.com',
        })

    def _create_profile(self, **extra_vals):
        vals = {
            'partner_type': 'insurer',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
        }
        vals.update(extra_vals)
        return self.profile_model.create(vals)

    def test_auto_name_generation_on_create(self):
        """La création remplit le nom avec partenaire + type si laissé vide."""
        profile = self._create_profile()
        self.assertIn('Assistance Hexagone', profile.name)
        self.assertIn('Assureur', profile.name)

    def test_profile_reference_compute(self):
        """La référence concatène le nom partenaire et le type humain."""
        profile = self._create_profile()
        self.assertEqual(profile.profile_reference, 'Assistance Hexagone / Assureur')

    def test_sla_validation_requires_positive_values(self):
        """Un SLA négatif déclenche une ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_profile(partner_type='garage', sla_response_hours=-1)

    def test_name_get_includes_type_label(self):
        """Le name_get ajoute le libellé humain du type partenaire."""
        profile = self._create_profile(partner_type='tow')
        display_name = profile.name_get()[0][1]
        self.assertIn('Remorqueur', display_name)


@tagged('post_install', '-at_install')
class TestFleetPartnerProfile(TransactionCase):
    """Valider la création de profils et l'intégration partenaire."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Garage Riviera',
            'is_company': True,
            'email': 'riviera@example.com',
        })
        cls.profile = cls.env['fleet.partner.profile'].create({
            'partner_type': 'garage',
            'partner_id': cls.partner.id,
            'company_id': cls.env.company.id,
            'sla_response_hours': 2.0,
            'sla_resolution_hours': 12.0,
        })

    def test_partner_profile_count_and_reference(self):
        """Le partenaire reflète correctement ses profils Fleet."""
        self.assertEqual(self.partner.fleet_partner_profile_count, 1)
        self.assertEqual(self.partner.fleet_partner_reference, self.profile.profile_reference)

    def test_action_view_profiles_domain(self):
        """L'action filtre sur le partenaire courant et prépare le contexte."""
        action = self.partner.action_view_fleet_partner_profiles()
        self.assertEqual(action['domain'], [('partner_id', '=', self.partner.id)])
        self.assertEqual(action['context'].get('default_partner_id'), self.partner.id)

    def test_action_create_profile_context(self):
        """L'action de création pré-remplit le partenaire."""
        action = self.partner.action_create_fleet_partner_profile()
        self.assertEqual(action['context'].get('default_partner_id'), self.partner.id)

    def test_partner_summary_prefers_active_profile(self):
        """La synthèse privilégie le profil actif le plus récent."""
        inactive_profile = self.env['fleet.partner.profile'].create({
            'partner_type': 'insurer',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'active': False,
        })
        contact = self.env['res.partner'].create({
            'name': 'Responsable Fleet',
            'email': 'contact@example.com',
        })
        active_profile = self.env['fleet.partner.profile'].create({
            'partner_type': 'tow',
            'partner_id': self.partner.id,
            'company_id': self.env.company.id,
            'contact_id': contact.id,
        })
        self.partner.invalidate_recordset(['fleet_partner_reference', 'fleet_partner_contact_id'])
        self.assertEqual(self.partner.fleet_partner_reference, active_profile.profile_reference)
        self.assertEqual(self.partner.fleet_partner_contact_id, contact)
        inactive_profile.unlink()
        active_profile.unlink()

    def test_action_create_profile_defaults_type_for_approved_partner(self):
        """Les partenaires approuvés utilisent 'insurer' par défaut dans l'action."""
        approved_partner = self.env['res.partner'].create({
            'name': 'Assureur Atlantique',
            'supplier_approved': True,
        })
        action = approved_partner.action_create_fleet_partner_profile()
        self.assertEqual(action['context'].get('default_partner_type'), 'insurer')

    def test_multi_company_rule_isolation(self):
        """Un utilisateur limité à une société ne voit que ses profils."""
        company_b = self.env['res.company'].create({'name': 'Fleet SOUTH'})
        partner_common = self.env['res.partner'].create({'name': 'Garage Sud'})
        profile_company_a = self.env['fleet.partner.profile'].create({
            'partner_type': 'insurer',
            'partner_id': partner_common.id,
            'company_id': self.env.company.id,
        })
        profile_company_b = self.env['fleet.partner.profile'].create({
            'partner_type': 'tow',
            'partner_id': partner_common.id,
            'company_id': company_b.id,
        })

        group_user = self.env.ref('custom_fleet_partner_network.group_fleet_partner_user')
        base_group = self.env.ref('base.group_user')
        user_b = self.env['res.users'].create({
            'name': 'Fleet South User',
            'login': 'fleet.south@example.com',
            'email': 'fleet.south@example.com',
            'company_id': company_b.id,
            'company_ids': [(6, 0, [company_b.id])],
            'groups_id': [(6, 0, [base_group.id, group_user.id])],
        })

        profiles_for_user_b = self.env['fleet.partner.profile'].with_user(user_b).search([])
        self.assertEqual(profiles_for_user_b, profile_company_b)

        # Clean up to keep TransactionCase deterministic
        profile_company_a.unlink()
        profile_company_b.unlink()
