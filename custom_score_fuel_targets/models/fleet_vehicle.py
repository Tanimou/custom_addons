# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.vehicle with fuel expense history smart button (FR-023).

Adds:
- Fuel expense count and totals
- Action to view fuel history
"""

from odoo import _, api, fields, models


class FleetVehicleFuelHistory(models.Model):
    """Extend fleet.vehicle with fuel expense history."""
    
    _inherit = 'fleet.vehicle'

    # -------------------------------------------------------------------------
    # FUEL HISTORY FIELDS
    # -------------------------------------------------------------------------
    fuel_expense_ids = fields.One2many(
        comodel_name='fleet.fuel.expense',
        inverse_name='vehicle_id',
        string="Dépenses carburant",
    )
    
    fuel_expense_count = fields.Integer(
        string="Nb pleins",
        compute="_compute_fuel_expense_stats",
        store=False,
        help="Nombre total de dépenses carburant enregistrées",
    )
    
    total_fuel_amount = fields.Monetary(
        string="Total carburant (€)",
        compute="_compute_fuel_expense_stats",
        store=False,
        currency_field='currency_id',
        help="Montant total des dépenses carburant",
    )
    
    total_fuel_liters = fields.Float(
        string="Total litres",
        compute="_compute_fuel_expense_stats",
        store=False,
        digits=(12, 2),
        help="Volume total de carburant consommé",
    )

    # For monetary field
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Devise",
        default=lambda self: self.env.company.currency_id,
    )

    # -------------------------------------------------------------------------
    # CONSUMPTION ALERT SUMMARY
    # -------------------------------------------------------------------------
    active_consumption_alert = fields.Selection(
        selection=[
            ('non_calculable', 'Non calculable'),
            ('ok', 'OK'),
            ('warning', 'Attention'),
            ('critical', 'Critique'),
        ],
        string="Alerte conso actuelle",
        compute="_compute_active_consumption_alert",
        store=False,
        help="Niveau d'alerte de consommation le plus récent",
    )

    # -------------------------------------------------------------------------
    # COMPUTED METHODS
    # -------------------------------------------------------------------------
    @api.depends('fuel_expense_ids', 'fuel_expense_ids.state')
    def _compute_fuel_expense_stats(self):
        """Compute fuel expense statistics."""
        FuelExpense = self.env['fleet.fuel.expense']
        
        for vehicle in self:
            # Only count validated expenses
            expenses = FuelExpense.search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'done'),
            ])
            
            vehicle.fuel_expense_count = len(expenses)
            vehicle.total_fuel_amount = sum(expenses.mapped('amount_total'))
            vehicle.total_fuel_liters = sum(expenses.mapped('liter_qty'))

    def _compute_active_consumption_alert(self):
        """Get most recent consumption alert from fuel summaries."""
        Summary = self.env['fleet.fuel.monthly.summary']
        
        for vehicle in self:
            # Get most recent summary with alert level
            latest_summary = Summary.search([
                ('vehicle_id', '=', vehicle.id),
                ('consumption_alert_level', '!=', False),
            ], order='year desc, month desc', limit=1)
            
            vehicle.active_consumption_alert = (
                latest_summary.consumption_alert_level if latest_summary else False
            )

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_fuel_expenses(self):
        """Open fuel expenses for this vehicle."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Historique carburant - %s", self.name),
            'res_model': 'fleet.fuel.expense',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'search_default_state_done': 1,
            },
        }

    def action_view_fuel_summaries(self):
        """Open fuel summaries for this vehicle."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Synthèses carburant - %s", self.name),
            'res_model': 'fleet.fuel.monthly.summary',
            'view_mode': 'tree,form,pivot',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
            },
        }
