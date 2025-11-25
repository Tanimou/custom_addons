# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class SupplierCategory(models.Model):
    """Supplier Category for classification (supplies, services, works, etc.)"""
    _name = 'supplier.category'
    _description = 'Supplier Category'
    _order = 'name'

    name = fields.Char(
        string='Nom de la catégorie',
        required=True,
        translate=True,
        help="Nom de la catégorie de fournisseur (par exemple, Fournitures de bureau, Services informatiques, Travaux de construction)"
    )
    code = fields.Char(
        string='Code',
        help="Code court pour la catégorie"
    )
    description = fields.Text(
        string='Description',
        translate=True,
        help="Description détaillée de cette catégorie de fournisseur"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Si décoché, cette catégorie sera masquée"
    )
    partner_count = fields.Integer(
        string='Nombre de fournisseurs',
        compute='_compute_partner_count',
        help="Nombre de fournisseur dans cette catégorie"
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code de la catégorie doit être unique.'),
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
            'name': _('Fournisseurs dans %s', self.name),
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
