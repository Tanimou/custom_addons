# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.maintenance.intervention for SCORE downtime KPIs (FR-019).

Adds:
- downtime_hours: Stored computed field for intervention downtime
- downtime_days: Stored computed field for downtime in days
- analytic_account_id: For project/department cost attribution (FR-026)
- Logic: Uses actual_start/actual_end if available, falls back to scheduled
"""

from datetime import datetime

from odoo import api, fields, models


class FleetMaintenanceInterventionDowntime(models.Model):
    """Extend maintenance intervention with downtime KPI fields (FR-019)."""

    _inherit = 'fleet.maintenance.intervention'

    # =========================================================================
    # ANALYTIC ACCOUNT FOR COST ATTRIBUTION (FR-026)
    # =========================================================================
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string="Compte analytique",
        tracking=True,
        help="Projet ou département pour l'imputation des coûts de maintenance"
    )

    # =========================================================================
    # DOWNTIME FIELDS (FR-019)
    # =========================================================================
    
    downtime_hours = fields.Float(
        string="Temps d'arrêt (h)",
        compute='_compute_downtime',
        store=True,
        help="Durée d'immobilisation du véhicule en heures. "
             "Calculé à partir des dates réelles si disponibles, sinon des dates planifiées."
    )
    
    downtime_days = fields.Float(
        string="Temps d'arrêt (j)",
        compute='_compute_downtime',
        store=True,
        help="Durée d'immobilisation du véhicule en jours."
    )
    
    is_curative = fields.Boolean(
        string="Curative",
        compute='_compute_typology_helpers',
        store=True,
        help="True if intervention is curative type"
    )
    
    is_preventive = fields.Boolean(
        string="Préventive",
        compute='_compute_typology_helpers',
        store=True,
        help="True if intervention is preventive type"
    )
    
    # =========================================================================
    # TECHNICIAN TIME FIELDS (FR-022)
    # =========================================================================
    
    technician_time_ids = fields.One2many(
        'fleet.maintenance.technician.time',
        'intervention_id',
        string="Temps techniciens",
        help="Enregistrements du temps passé par les techniciens"
    )
    
    total_technician_hours = fields.Float(
        string="Total heures techniciens",
        compute='_compute_total_technician_hours',
        store=True,
        help="Somme des heures travaillées par tous les techniciens"
    )
    
    technician_count = fields.Integer(
        string="Nombre techniciens",
        compute='_compute_total_technician_hours',
        store=True,
        help="Nombre de techniciens ayant travaillé sur cette intervention"
    )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('actual_start', 'actual_end', 'scheduled_start', 'scheduled_end', 'state')
    def _compute_downtime(self):
        """
        Compute downtime in hours and days.
        
        Logic:
        1. If actual_start and actual_end exist, use them
        2. If only actual_start exists (ongoing), calculate until now
        3. Otherwise, fall back to scheduled dates
        4. Return 0 if no dates available
        5. Never return negative values
        """
        now = fields.Datetime.now()
        
        for record in self:
            start_dt = None
            end_dt = None
            
            # Priority 1: Use actual dates
            if record.actual_start:
                start_dt = record.actual_start
                end_dt = record.actual_end or now  # If no end, use current time
            # Priority 2: Fall back to scheduled dates
            elif record.scheduled_start:
                start_dt = record.scheduled_start
                end_dt = record.scheduled_end or now
            
            # Calculate duration
            if start_dt and end_dt:
                delta = end_dt - start_dt
                hours = delta.total_seconds() / 3600.0
                # Never return negative
                record.downtime_hours = max(0.0, hours)
                record.downtime_days = max(0.0, hours / 24.0)
            else:
                record.downtime_hours = 0.0
                record.downtime_days = 0.0

    @api.depends('intervention_type')
    def _compute_typology_helpers(self):
        """Compute helper booleans for typology filtering."""
        for record in self:
            record.is_curative = record.intervention_type == 'curative'
            record.is_preventive = record.intervention_type == 'preventive'

    @api.depends('technician_time_ids', 'technician_time_ids.hours')
    def _compute_total_technician_hours(self):
        """Compute total technician hours and count."""
        for record in self:
            time_entries = record.technician_time_ids
            record.total_technician_hours = sum(time_entries.mapped('hours'))
            record.technician_count = len(time_entries.mapped('technician_id'))

    # =========================================================================
    # ACTIONS
    # =========================================================================
    
    def action_view_technician_time(self):
        """Open technician time entries for this intervention."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Temps Techniciens - {self.name}",
            'res_model': 'fleet.maintenance.technician.time',
            'view_mode': 'tree,form',
            'domain': [('intervention_id', '=', self.id)],
            'context': {'default_intervention_id': self.id},
        }
