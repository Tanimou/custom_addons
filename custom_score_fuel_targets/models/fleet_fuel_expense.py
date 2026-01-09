# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.fuel.expense with category reference.
"""

from odoo import fields, models


class FleetFuelExpenseCategory(models.Model):
    """Extend fuel expense with vehicle category reference."""
    
    _inherit = 'fleet.fuel.expense'

    vehicle_category_id = fields.Many2one(
        related='vehicle_id.category_id',
        string="Famille véhicule",
        store=True,
        help="Catégorie/famille du véhicule (pour filtrage)",
    )
