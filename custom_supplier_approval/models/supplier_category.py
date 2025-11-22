# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class SupplierCategory(models.Model):
    """Supplier Category for classification (supplies, services, works, etc.)"""
    _name = 'supplier.category'
    _description = 'Supplier Category'
    _order = 'name'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        help="Name of the supplier category (e.g., Office Supplies, IT Services, Construction Works)"
    )
    code = fields.Char(
        string='Code',
        help="Short code for the category"
    )
    description = fields.Text(
        string='Description',
        translate=True,
        help="Detailed description of this supplier category"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this category will be hidden"
    )
    partner_count = fields.Integer(
        string='Number of Suppliers',
        compute='_compute_partner_count',
        help="Number of suppliers in this category"
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'The category code must be unique!'),
    ]

    def _compute_partner_count(self):
        """Compute the number of suppliers in each category"""
        for category in self:
            category.partner_count = self.env['res.partner'].search_count([
                ('supplier_category_ids', 'in', category.id),
                ('supplier_rank', '>', 0)
            ])

    def action_view_suppliers(self):
        """Action to view all suppliers in this category"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Suppliers in %s', self.name),
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [
                ('supplier_category_ids', 'in', self.id),
                ('supplier_rank', '>', 0)
            ],
            'context': {
                'default_supplier_category_ids': [(4, self.id)],
                'search_default_supplier': 1,
            }
        }
