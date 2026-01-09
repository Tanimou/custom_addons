# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Technician time tracking model for maintenance interventions (FR-022).

Tracks:
- Hours worked by each technician on each intervention
- Date of work
- Type of work performed
- Notes and description
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FleetMaintenanceTechnicianTime(models.Model):
    """Track technician time spent on maintenance interventions (FR-022)."""

    _name = 'fleet.maintenance.technician.time'
    _description = "Temps technicien maintenance"
    _order = 'date desc, id desc'
    _inherit = ['mail.thread']

    # =========================================================================
    # CORE FIELDS
    # =========================================================================
    
    intervention_id = fields.Many2one(
        'fleet.maintenance.intervention',
        string="Intervention",
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
    )
    
    technician_id = fields.Many2one(
        'res.users',
        string="Technicien",
        required=True,
        tracking=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    
    hours = fields.Float(
        string="Heures",
        required=True,
        default=1.0,
        tracking=True,
        help="Nombre d'heures travaillées",
    )
    
    work_type = fields.Selection(
        selection=[
            ('diagnostic', 'Diagnostic'),
            ('repair', 'Réparation'),
            ('replacement', 'Remplacement'),
            ('inspection', 'Inspection'),
            ('cleaning', 'Nettoyage'),
            ('testing', 'Tests'),
            ('other', 'Autre'),
        ],
        string="Type de travail",
        default='repair',
    )
    
    description = fields.Text(
        string="Description",
        help="Description du travail effectué",
    )

    # =========================================================================
    # RELATED FIELDS
    # =========================================================================
    
    vehicle_id = fields.Many2one(
        related='intervention_id.vehicle_id',
        store=True,
        string="Véhicule",
    )
    
    intervention_type = fields.Selection(
        related='intervention_id.intervention_type',
        store=True,
        string="Type intervention",
    )
    
    intervention_state = fields.Selection(
        related='intervention_id.state',
        store=True,
        string="État intervention",
    )
    
    company_id = fields.Many2one(
        related='intervention_id.company_id',
        store=True,
        string="Société",
    )

    # =========================================================================
    # DISPLAY FIELDS
    # =========================================================================
    
    name = fields.Char(
        string="Référence",
        compute='_compute_name',
        store=True,
    )
    
    technician_name = fields.Char(
        related='technician_id.name',
        string="Nom technicien",
    )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('intervention_id.name', 'technician_id.name', 'date')
    def _compute_name(self):
        """Generate display name for the time entry."""
        for record in self:
            parts = []
            if record.intervention_id:
                parts.append(record.intervention_id.name or '')
            if record.technician_id:
                parts.append(record.technician_id.name or '')
            if record.date:
                parts.append(record.date.strftime('%d/%m/%Y'))
            record.name = ' - '.join(filter(None, parts)) or '/'

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    
    @api.constrains('hours')
    def _check_hours(self):
        """Ensure hours is positive and reasonable."""
        for record in self:
            if record.hours <= 0:
                raise ValidationError("Le nombre d'heures doit être positif.")
            if record.hours > 24:
                raise ValidationError(
                    "Le nombre d'heures ne peut pas dépasser 24 pour une seule entrée."
                )

    @api.constrains('date')
    def _check_date(self):
        """Ensure date is not in the future."""
        today = fields.Date.context_today(self)
        for record in self:
            if record.date > today:
                raise ValidationError(
                    "La date de travail ne peut pas être dans le futur."
                )

    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================
    
    def action_view_intervention(self):
        """Open the related intervention form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.maintenance.intervention',
            'res_id': self.intervention_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
