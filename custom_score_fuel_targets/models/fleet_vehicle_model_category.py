# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.vehicle.model.category to add consumption target (FR-024).

This allows setting a target L/100km for each vehicle family/category.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicleModelCategoryTarget(models.Model):
    """Extend vehicle model category with fuel consumption target."""
    
    _inherit = 'fleet.vehicle.model.category'

    # -------------------------------------------------------------------------
    # TARGET CONSUMPTION FIELDS
    # -------------------------------------------------------------------------
    target_consumption_l100km = fields.Float(
        string="Cible L/100km",
        digits=(6, 2),
        help="Consommation cible en litres pour 100 km. "
             "Utilisé pour calculer les écarts et alertes de surconsommation.",
    )
    
    target_consumption_notes = fields.Text(
        string="Notes cible",
        help="Notes sur la cible de consommation (conditions, sources, etc.)",
    )
    
    # -------------------------------------------------------------------------
    # RELATED COUNTS
    # -------------------------------------------------------------------------
    vehicle_count = fields.Integer(
        string="Nombre de véhicules",
        compute="_compute_vehicle_count",
    )
    
    summary_alert_count = fields.Integer(
        string="Alertes consommation",
        compute="_compute_summary_alert_count",
        help="Nombre de synthèses avec alerte consommation active",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('target_consumption_l100km')
    def _check_target_positive(self):
        """Ensure target consumption is positive or zero."""
        for category in self:
            if category.target_consumption_l100km and category.target_consumption_l100km < 0:
                raise ValidationError(_(
                    "La cible de consommation doit être positive ou nulle. "
                    "Valeur reçue: %(value)s L/100km",
                    value=category.target_consumption_l100km
                ))

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS
    # -------------------------------------------------------------------------
    def _compute_vehicle_count(self):
        """Count vehicles in this category."""
        Vehicle = self.env['fleet.vehicle']
        for category in self:
            category.vehicle_count = Vehicle.search_count([
                ('category_id', '=', category.id)
            ])

    def _compute_summary_alert_count(self):
        """Count summaries with consumption alerts for vehicles in this category."""
        Summary = self.env['fleet.fuel.monthly.summary']
        for category in self:
            # Get vehicles in this category
            vehicles = self.env['fleet.vehicle'].search([
                ('category_id', '=', category.id)
            ])
            if vehicles:
                category.summary_alert_count = Summary.search_count([
                    ('vehicle_id', 'in', vehicles.ids),
                    ('consumption_alert_level', 'in', ['warning', 'critical']),
                    ('state', '!=', 'closed'),
                ])
            else:
                category.summary_alert_count = 0

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_vehicles(self):
        """Open vehicles in this category."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Véhicules - %s", self.name),
            'res_model': 'fleet.vehicle',
            'view_mode': 'tree,kanban,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

    def action_view_consumption_alerts(self):
        """Open fuel summaries with alerts for vehicles in this category."""
        self.ensure_one()
        vehicles = self.env['fleet.vehicle'].search([
            ('category_id', '=', self.id)
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _("Alertes consommation - %s", self.name),
            'res_model': 'fleet.fuel.monthly.summary',
            'view_mode': 'tree,form,pivot',
            'domain': [
                ('vehicle_id', 'in', vehicles.ids),
                ('consumption_alert_level', 'in', ['warning', 'critical']),
            ],
        }
