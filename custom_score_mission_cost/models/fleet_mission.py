# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Fleet Mission extension for SCORE Mission Cost module.

FR-013b/FR-013c: Approval traceability (existing fields in custom_fleet_management are sufficient)
FR-014: Mission expense consolidation via One2many
FR-015: Cost per kilometer KPI calculation
FR-026: Analytic account for project/department reporting
"""

from odoo import _, api, fields, models


class FleetMissionCost(models.Model):
    """Extension of fleet.mission for cost tracking and KPI calculation."""
    
    _inherit = 'fleet.mission'

    # ========== EXPENSE LINK ==========
    
    expense_ids = fields.One2many(
        'fleet.mission.expense',
        'mission_id',
        string='Dépenses',
        help="Liste des dépenses associées à cette mission"
    )
    
    expense_count = fields.Integer(
        string='Nombre de Dépenses',
        compute='_compute_expense_totals',
        store=True,
        help="Nombre total de dépenses enregistrées"
    )
    
    # ========== COST TOTALS ==========
    
    total_expenses = fields.Float(
        string='Total Dépenses',
        compute='_compute_expense_totals',
        store=True,
        digits='Product Price',
        help="Somme de toutes les dépenses de la mission"
    )
    
    total_toll = fields.Float(
        string='Total Péages',
        compute='_compute_expense_totals',
        store=True,
        digits='Product Price',
        help="Total des frais de péage"
    )
    
    total_fuel = fields.Float(
        string='Total Carburant',
        compute='_compute_expense_totals',
        store=True,
        digits='Product Price',
        help="Total des frais de carburant"
    )
    
    total_maintenance = fields.Float(
        string='Total Entretien',
        compute='_compute_expense_totals',
        store=True,
        digits='Product Price',
        help="Total des frais d'entretien"
    )
    
    total_other = fields.Float(
        string='Total Autres',
        compute='_compute_expense_totals',
        store=True,
        digits='Product Price',
        help="Total des autres frais (parking, hébergement, repas, etc.)"
    )
    
    # ========== COST PER KM KPI (FR-015) ==========
    
    cost_per_km = fields.Float(
        string='Coût / km',
        compute='_compute_cost_per_km',
        store=True,
        digits=(12, 4),
        help="Coût par kilomètre = Total Dépenses / Distance parcourue"
    )
    
    cost_per_km_display = fields.Char(
        string='Coût / km',
        compute='_compute_cost_per_km_display',
        help="Affichage formaté du coût par km"
    )
    
    # ========== ANALYTIC (FR-026) ==========
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Compte Analytique',
        tracking=True,
        help="Compte analytique pour le reporting par projet/département"
    )
    
    # ========== COMPUTED METHODS ==========
    
    @api.depends('expense_ids', 'expense_ids.amount', 'expense_ids.expense_type')
    def _compute_expense_totals(self):
        """Compute expense totals by type and overall."""
        for mission in self:
            expenses = mission.expense_ids
            
            mission.expense_count = len(expenses)
            mission.total_expenses = sum(expenses.mapped('amount'))
            
            # Group by type
            mission.total_toll = sum(
                exp.amount for exp in expenses if exp.expense_type == 'toll'
            )
            mission.total_fuel = sum(
                exp.amount for exp in expenses if exp.expense_type == 'fuel'
            )
            mission.total_maintenance = sum(
                exp.amount for exp in expenses if exp.expense_type == 'maintenance'
            )
            # Other = parking, accommodation, meal, other
            mission.total_other = sum(
                exp.amount for exp in expenses 
                if exp.expense_type in ('parking', 'accommodation', 'meal', 'other')
            )
    
    @api.depends('total_expenses', 'distance_km')
    def _compute_cost_per_km(self):
        """
        Compute cost per kilometer.
        
        FR-015: Cost/km = Total Expenses / Distance
        Returns 0.0 if distance is zero or not calculable (non-blocking).
        """
        for mission in self:
            if mission.distance_km and mission.distance_km > 0:
                mission.cost_per_km = mission.total_expenses / mission.distance_km
            else:
                mission.cost_per_km = 0.0
    
    @api.depends('cost_per_km', 'distance_km')
    def _compute_cost_per_km_display(self):
        """Format cost per km for display, showing 'N/C' if not calculable."""
        for mission in self:
            if not mission.distance_km or mission.distance_km <= 0:
                mission.cost_per_km_display = _("N/C (pas de km)")
            elif mission.cost_per_km == 0.0 and mission.total_expenses == 0.0:
                mission.cost_per_km_display = _("N/C (pas de dépenses)")
            else:
                mission.cost_per_km_display = f"{mission.cost_per_km:.4f} / km"
    
    # ========== ACTION METHODS ==========
    
    def action_view_expenses(self):
        """Open expense list view for this mission."""
        self.ensure_one()
        return {
            'name': _("Dépenses: %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.mission.expense',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('mission_id', '=', self.id)],
            'context': {
                'default_mission_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
            },
        }
    
    def action_add_expense(self):
        """Open expense creation wizard/form."""
        self.ensure_one()
        return {
            'name': _("Nouvelle Dépense"),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.mission.expense',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mission_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
            },
        }
    
    # ========== PROPAGATE ANALYTIC TO EXPENSES ==========
    
    def write(self, vals):
        """Propagate analytic account changes to linked expenses."""
        res = super().write(vals)
        
        if 'analytic_account_id' in vals:
            # Optionally propagate to expenses that don't have one set
            for mission in self:
                expenses_without_analytic = mission.expense_ids.filtered(
                    lambda e: not e.analytic_account_id
                )
                if expenses_without_analytic and vals.get('analytic_account_id'):
                    expenses_without_analytic.write({
                        'analytic_account_id': vals['analytic_account_id']
                    })
        
        return res
