# -*- coding: utf-8 -*-
"""Extension de res.partner pour le réseau de partenaires Fleet."""

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fleet_partner_profile_ids = fields.One2many(
        'fleet.partner.profile',
        'partner_id',
        string='Profils Parc Auto',
        readonly=True,
    )
    fleet_partner_profile_count = fields.Integer(
        string='Nombre de profils Fleet',
        compute='_compute_fleet_partner_profile_count',
    )
    fleet_partner_reference = fields.Char(
        string='Référence Parc Auto',
        compute='_compute_fleet_partner_summary',
    )
    fleet_partner_contact_id = fields.Many2one(
        'res.partner',
        string='Contact Fleet',
        compute='_compute_fleet_partner_summary',
    )

    @api.depends('fleet_partner_profile_ids')
    def _compute_fleet_partner_profile_count(self):
        counts = {partner_id: 0 for partner_id in self.ids}
        if self.ids:
            data = self.env['fleet.partner.profile'].read_group(
                [('partner_id', 'in', self.ids)],
                ['partner_id'],
                ['partner_id'],
            )
            for entry in data:
                partner_id = entry['partner_id'][0]
                counts[partner_id] = entry['partner_id_count']
        for partner in self:
            partner.fleet_partner_profile_count = counts.get(partner.id, 0)

    @api.depends(
        'fleet_partner_profile_ids.profile_reference',
        'fleet_partner_profile_ids.contact_id',
        'fleet_partner_profile_ids.active',
        'fleet_partner_profile_ids.company_id',
    )
    def _compute_fleet_partner_summary(self):
        summary = {}
        if self.ids:
            profiles = self.env['fleet.partner.profile'].search(
                [('partner_id', 'in', self.ids)],
                order='active desc, write_date desc',
            )
            for profile in profiles:
                partner_id = profile.partner_id.id
                if partner_id not in summary:
                    summary[partner_id] = profile
        for partner in self:
            profile = summary.get(partner.id)
            partner.fleet_partner_reference = profile.profile_reference if profile else False
            partner.fleet_partner_contact_id = profile.contact_id if profile else False

    def action_view_fleet_partner_profiles(self):
        self.ensure_one()
        action = self.env.ref('custom_fleet_partner_network.action_fleet_partner_profile').read()[0]
        action['domain'] = [('partner_id', '=', self.id)]
        context = safe_eval(action.get('context', '{}'))
        context.update({'default_partner_id': self.id})
        action['context'] = context
        return action

    def action_create_fleet_partner_profile(self):
        self.ensure_one()
        action = self.env.ref('custom_fleet_partner_network.action_fleet_partner_profile').read()[0]
        action['view_mode'] = 'form'
        action['views'] = [(False, 'form')]
        context = {
            'default_partner_id': self.id,
            'default_partner_type': 'assureur' if self.supplier_approved else False,
        }
        action['domain'] = [('id', '=', False)]
        action['context'] = context
        return action
