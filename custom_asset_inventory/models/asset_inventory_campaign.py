# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Model: asset.inventory.campaign
================================

Campagne d'inventaire des immobilisations.

Ce modèle représente une campagne d'inventaire physique des immobilisations,
avec une période définie, une périodicité, et des emplacements cibles.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssetInventoryCampaign(models.Model):
    """Campagne d'inventaire des immobilisations."""

    _name = 'asset.inventory.campaign'
    _description = "Campagne d'inventaire des immobilisations"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    # Identification
    name = fields.Char(
        string="Nom",
        required=True,
        tracking=True,
        help="Nom de la campagne d'inventaire",
    )
    code = fields.Char(
        string="Code",
        copy=False,
        help="Code unique de la campagne (généré automatiquement si vide)",
    )
    
    # Dates
    date_start = fields.Date(
        string="Date de début",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Date de début de la campagne d'inventaire",
    )
    date_end = fields.Date(
        string="Date de fin",
        required=True,
        tracking=True,
        help="Date de fin prévue de la campagne d'inventaire",
    )
    
    # Périodicité
    periodicity = fields.Selection(
        selection=[
            ('monthly', 'Mensuelle'),
            ('quarterly', 'Trimestrielle'),
            ('yearly', 'Annuelle'),
        ],
        string="Périodicité",
        default='yearly',
        tracking=True,
        help="Fréquence recommandée pour les inventaires de ce type",
    )
    
    # Organisation
    team_id = fields.Many2one(
        comodel_name='hr.department',
        string="Équipe responsable",
        tracking=True,
        help="Département responsable de la réalisation de l'inventaire",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help="Société concernée par cette campagne d'inventaire",
    )
    
    # Localisation
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Entrepôt",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help="Entrepôt principal concerné par l'inventaire",
    )
    location_ids = fields.Many2many(
        comodel_name='stock.location',
        relation='asset_inventory_campaign_location_rel',
        column1='campaign_id',
        column2='location_id',
        string="Emplacements",
        domain="[('company_id', 'in', [company_id, False])]",
        help="Emplacements spécifiques à inventorier",
    )
    
    # État
    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('in_progress', 'En cours'),
            ('done', 'Terminé'),
            ('cancel', 'Annulé'),
        ],
        string="État",
        default='draft',
        required=True,
        tracking=True,
        help="État de la campagne d'inventaire",
    )
    
    # Lignes d'inventaire
    line_ids = fields.One2many(
        comodel_name='asset.inventory.line',
        inverse_name='campaign_id',
        string="Lignes d'inventaire",
        help="Lignes d'inventaire associées à cette campagne",
    )
    
    # Champs calculés pour statistiques
    line_count = fields.Integer(
        string="Nombre de lignes",
        compute='_compute_line_stats',
        store=True,
    )
    line_present_count = fields.Integer(
        string="Immobilisations présentes",
        compute='_compute_line_stats',
        store=True,
    )
    line_missing_count = fields.Integer(
        string="Immobilisations manquantes",
        compute='_compute_line_stats',
        store=True,
    )
    progress_percent = fields.Float(
        string="Progression (%)",
        compute='_compute_line_stats',
        store=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('line_ids', 'line_ids.physical_status')
    def _compute_line_stats(self):
        """Calcule les statistiques des lignes d'inventaire."""
        for campaign in self:
            lines = campaign.line_ids
            campaign.line_count = len(lines)
            campaign.line_present_count = len(lines.filtered(
                lambda l: l.physical_status == 'present'
            ))
            campaign.line_missing_count = len(lines.filtered(
                lambda l: l.physical_status == 'missing'
            ))
            # Progression = lignes avec statut renseigné / total
            lines_with_status = lines.filtered(lambda l: l.physical_status)
            campaign.progress_percent = (
                (len(lines_with_status) / len(lines) * 100)
                if lines else 0.0
            )

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Vérifie que la date de fin est postérieure à la date de début."""
        for campaign in self:
            if campaign.date_start and campaign.date_end:
                if campaign.date_end < campaign.date_start:
                    raise ValidationError(_(
                        "La date de fin doit être postérieure à la date de début."
                    ))

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """Met à jour le domaine des emplacements selon l'entrepôt sélectionné."""
        if self.warehouse_id:
            # Réinitialiser les emplacements si l'entrepôt change
            self.location_ids = False
            return {
                'domain': {
                    'location_ids': [
                        ('company_id', 'in', [self.company_id.id, False]),
                        '|',
                        ('warehouse_id', '=', self.warehouse_id.id),
                        ('warehouse_id', '=', False),
                    ]
                }
            }

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Génère le code automatiquement si non fourni."""
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'asset.inventory.campaign'
                ) or _('Nouveau')
        return super().create(vals_list)

    def copy(self, default=None):
        """Personnalise la copie d'une campagne."""
        self.ensure_one()
        default = dict(default or {})
        default.update({
            'name': _("%s (copie)") % self.name,
            'code': False,  # Sera regénéré
            'state': 'draft',
            'date_start': fields.Date.context_today(self),
            'date_end': False,
        })
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    def action_start(self):
        """Démarre la campagne d'inventaire."""
        for campaign in self:
            if campaign.state != 'draft':
                raise UserError(_(
                    "Seules les campagnes en brouillon peuvent être démarrées."
                ))
            if not campaign.line_ids:
                raise UserError(_(
                    "Veuillez générer les lignes d'inventaire avant de démarrer "
                    "la campagne. Utilisez le bouton 'Générer les lignes'."
                ))
            campaign.state = 'in_progress'
        return True

    def action_done(self):
        """Termine la campagne d'inventaire."""
        for campaign in self:
            if campaign.state != 'in_progress':
                raise UserError(_(
                    "Seules les campagnes en cours peuvent être terminées."
                ))
            # Vérifier que toutes les lignes ont un statut
            lines_without_status = campaign.line_ids.filtered(
                lambda l: not l.physical_status
            )
            if lines_without_status:
                raise UserError(_(
                    "Toutes les lignes doivent avoir un statut physique renseigné "
                    "avant de terminer la campagne. %d ligne(s) sans statut."
                ) % len(lines_without_status))
            campaign.state = 'done'
        return True

    def action_cancel(self):
        """Annule la campagne d'inventaire."""
        for campaign in self:
            if campaign.state == 'done':
                raise UserError(_(
                    "Les campagnes terminées ne peuvent pas être annulées."
                ))
            campaign.state = 'cancel'
        return True

    def action_draft(self):
        """Remet la campagne en brouillon."""
        for campaign in self:
            if campaign.state not in ('cancel', 'in_progress'):
                raise UserError(_(
                    "Seules les campagnes annulées ou en cours peuvent être "
                    "remises en brouillon."
                ))
            campaign.state = 'draft'
        return True

    def action_generate_lines(self):
        """Ouvre l'assistant de génération des lignes d'inventaire."""
        self.ensure_one()
        return {
            'name': _("Générer les lignes d'inventaire"),
            'type': 'ir.actions.act_window',
            'res_model': 'asset.inventory.generate.lines',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_campaign_id': self.id,
                'default_warehouse_id': self.warehouse_id.id,
                'default_location_ids': [(6, 0, self.location_ids.ids)],
            },
        }

    def action_view_lines(self):
        """Affiche les lignes d'inventaire de la campagne."""
        self.ensure_one()
        return {
            'name': _("Lignes d'inventaire"),
            'type': 'ir.actions.act_window',
            'res_model': 'asset.inventory.line',
            'view_mode': 'list,form',
            'domain': [('campaign_id', '=', self.id)],
            'context': {'default_campaign_id': self.id},
        }
