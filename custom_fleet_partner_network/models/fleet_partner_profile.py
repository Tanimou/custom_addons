# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetPartnerProfile(models.Model):
    """Master data for strategic partners (assureurs, garages, remorqueurs)."""

    _name = 'fleet.partner.profile'
    _description = 'Profil Partenaire Parc Automobile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_type, name'

    PARTNER_TYPES = [
        ('assureur', 'Assureur'),
        ('garage', 'Garage Agréé'),
        ('remorqueur', 'Remorqueur'),
    ]

    partner_type = fields.Selection(
        selection=PARTNER_TYPES,  # type: ignore[arg-type]
        string='Type de partenaire',
        required=True,
        tracking=True,
        index=True,
    )
    name = fields.Char(
        string='Libellé',
        required=True,
        tracking=True,
        default=lambda self: _('Nouveau'),
        index=True,
        help="Nom court du profil partenaire (ex: Assurance AXA Nord)."
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
        help='Contact fournisseur approuvé via le module supplier approval.'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    contact_id = fields.Many2one(
        'res.partner',
        string='Contact principal',
        tracking=True,
        help='Contact opérationnel principal côté partenaire (remonté sur les incidents).'
    )
    color = fields.Integer(string='Couleur Kanban', default=0)
    active = fields.Boolean(string='Actif', default=True)

    service_area_ids = fields.Many2many(
        'res.country.state',
        'fleet_partner_profile_state_rel',
        'profile_id',
        'state_id',
        string="Zones d'intervention",
        tracking=True,
        help='Régions ou états couverts par ce partenaire.'
    )
    service_ids = fields.Many2many(
        'fleet.service.type',
        'fleet_partner_profile_service_rel',
        'profile_id',
        'service_id',
        string='Services pris en charge',
        help='Types d’intervention que ce partenaire peut assurer (remorquage, carrosserie…).'
    )
    sla_response_hours = fields.Float(
        string='SLA réponse (h)',
        tracking=True,
        digits=(16, 2),
        help='Temps maximal pour accuser réception ou dépêcher une équipe.'
    )
    sla_resolution_hours = fields.Float(
        string='SLA résolution (h)',
        tracking=True,
        digits=(16, 2),
        help='Temps maximal pour résoudre l’incident ou finaliser la réparation.'
    )
    coverage_notes = fields.Text(
        string='Notes de couverture',
        help='Informations complémentaires : disponibilité 24/7, limitations, obligations contractuelles.'
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_partner_profile_attachment_rel',
        'profile_id',
        'attachment_id',
        string='Documents contractuels',
        help='Documents signés, polices, conventions, etc.'
    )

    supplier_approved = fields.Boolean(
        string='Partenaire approuvé',
        related='partner_id.supplier_approved',
        store=True,
        readonly=True,
    )
    supplier_score = fields.Float(
        string='Score fournisseur (%)',
        related='partner_id.supplier_satisfaction_rate',
        store=True,
        readonly=True,
    )

    profile_reference = fields.Char(
        string='Référence partenaire',
        compute='_compute_profile_reference',
        store=True,
    )

    _sql_constraints = [
        (
            'partner_type_company_unique',
            'unique(partner_id, partner_type, company_id)',
            "Ce partenaire possède déjà un profil pour ce type et cette société.",
        )
    ]

    @api.depends('partner_id.display_name', 'partner_type')
    def _compute_profile_reference(self):
        """Technical reference used in kanban cards and smart buttons."""
        selection = dict(self.PARTNER_TYPES)
        for profile in self:
            partner_name = profile.partner_id.display_name or ''
            type_label = selection.get(profile.partner_type or '', '')
            if partner_name and type_label:
                profile.profile_reference = f"{partner_name} / {type_label}"
            else:
                profile.profile_reference = partner_name or type_label or _('Profil partenaire')

    @api.constrains('sla_response_hours', 'sla_resolution_hours')
    def _check_positive_sla(self):
        for profile in self:
            if profile.sla_response_hours and profile.sla_response_hours < 0:
                raise ValidationError(_('Le SLA de réponse doit être positif.'))
            if profile.sla_resolution_hours and profile.sla_resolution_hours < 0:
                raise ValidationError(_('Le SLA de résolution doit être positif.'))

    @api.model_create_multi
    def create(self, vals_list):
        selection = dict(self.PARTNER_TYPES)
        for vals in vals_list:
            if not vals.get('partner_type'):
                continue
            if not vals.get('name') or vals['name'] == _('Nouveau'):
                partner = False
                if vals.get('partner_id'):
                    partner = self.env['res.partner'].browse(vals['partner_id'])
                type_label = selection.get(vals['partner_type'] or '', '').strip()
                parts = []
                if partner:
                    parts.append(partner.display_name)
                if type_label:
                    parts.append(type_label)
                if parts:
                    vals['name'] = ' - '.join(parts)
        return super().create(vals_list)

    def name_get(self):
        selection = dict(self.PARTNER_TYPES)
        res = []
        for profile in self:
            base_name = profile.name if profile.name and profile.name != _('Nouveau') else profile.partner_id.display_name
            type_label = selection.get(profile.partner_type or '', '')
            display = base_name
            if type_label:
                display = f"{base_name} ({type_label})"
            res.append((profile.id, display))
        return res

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partenaire'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }
