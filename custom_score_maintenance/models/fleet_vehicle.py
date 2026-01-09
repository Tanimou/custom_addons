# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.vehicle for SCORE maintenance KPIs.

Adds:
- Total downtime aggregation from interventions
- Maintenance availability indicators
"""

from odoo import api, fields, models


class FleetVehicleMaintenanceKPI(models.Model):
    """Extend fleet.vehicle with maintenance KPI fields."""

    _inherit = 'fleet.vehicle'

    # =========================================================================
    # DOWNTIME KPI FIELDS
    # =========================================================================
    
    total_downtime_hours = fields.Float(
        string="Total temps d'arrêt (h)",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Total des heures d'arrêt pour maintenance"
    )
    
    total_downtime_days = fields.Float(
        string="Total temps d'arrêt (j)",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Total des jours d'arrêt pour maintenance"
    )
    
    mttr_hours = fields.Float(
        string="MTTR (h)",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Mean Time To Repair - Temps moyen de réparation en heures"
    )
    
    intervention_count_completed = fields.Integer(
        string="Interventions terminées",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Nombre d'interventions terminées"
    )
    
    intervention_count_curative = fields.Integer(
        string="Interventions curatives",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Nombre d'interventions curatives terminées"
    )
    
    intervention_count_preventive = fields.Integer(
        string="Interventions préventives",
        compute='_compute_maintenance_kpis',
        store=True,
        help="Nombre d'interventions préventives terminées"
    )
    
    has_active_intervention = fields.Boolean(
        string="Intervention en cours",
        compute='_compute_has_active_intervention',
        search='_search_has_active_intervention',
        help="Indique si le véhicule a une intervention en cours"
    )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('maintenance_history_ids', 'maintenance_history_ids.downtime_hours', 
                 'maintenance_history_ids.state', 'maintenance_history_ids.intervention_type')
    def _compute_maintenance_kpis(self):
        """Compute maintenance KPIs from intervention history."""
        for vehicle in self:
            # Get completed interventions
            completed = vehicle.maintenance_history_ids.filtered(
                lambda i: i.state == 'done'
            )
            
            # Total downtime
            total_hours = sum(completed.mapped('downtime_hours'))
            vehicle.total_downtime_hours = total_hours
            vehicle.total_downtime_days = total_hours / 24.0 if total_hours else 0.0
            
            # MTTR - only for curative
            curative = completed.filtered(lambda i: i.intervention_type == 'curative')
            if curative:
                vehicle.mttr_hours = sum(curative.mapped('downtime_hours')) / len(curative)
            else:
                vehicle.mttr_hours = 0.0
            
            # Counts
            vehicle.intervention_count_completed = len(completed)
            vehicle.intervention_count_curative = len(curative)
            vehicle.intervention_count_preventive = len(completed) - len(curative)

    @api.depends('maintenance_history_ids', 'maintenance_history_ids.state')
    def _compute_has_active_intervention(self):
        """Check if vehicle has an active (in_progress) intervention."""
        for vehicle in self:
            vehicle.has_active_intervention = bool(
                vehicle.maintenance_history_ids.filtered(
                    lambda i: i.state == 'in_progress'
                )
            )

    def _search_has_active_intervention(self, operator, value):
        """Search vehicles by active intervention status."""
        if operator not in ('=', '!='):
            raise ValueError("Unsupported operator for has_active_intervention search")
        
        # Find vehicles with in_progress interventions
        interventions = self.env['fleet.maintenance.intervention'].search([
            ('state', '=', 'in_progress'),
        ])
        vehicle_ids = interventions.mapped('vehicle_id').ids
        
        # Adjust based on operator and value
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', vehicle_ids)]
        else:
            return [('id', 'not in', vehicle_ids)]

    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================
    
    def action_view_downtime_report(self):
        """Open downtime pivot/graph report for this vehicle."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Temps d'arrêt - {self.name}",
            'res_model': 'fleet.maintenance.intervention',
            'view_mode': 'pivot,graph,tree',
            'domain': [('vehicle_id', '=', self.id), ('state', '=', 'done')],
            'context': {'search_default_group_intervention_type': 1},
        }
