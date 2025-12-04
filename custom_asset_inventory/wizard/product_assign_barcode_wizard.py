# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Assistant d'attribution de codes-barres aux produits.

Ce wizard permet d'attribuer des codes-barres uniques à une sélection de produits,
avec confirmation avant écrasement des codes-barres existants.
"""

import random
import time

from odoo import api, fields, models


class ProductAssignBarcodeWizard(models.TransientModel):
    """Wizard pour l'attribution de codes-barres aux produits."""

    _name = 'product.assign.barcode.wizard'
    _description = "Assistant d'attribution de codes-barres"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    product_ids = fields.Many2many(
        comodel_name='product.product',
        string="Produits sélectionnés",
        readonly=True,
    )
    
    count_total = fields.Integer(
        string="Total produits",
        compute='_compute_counts',
    )
    
    count_with_barcode = fields.Integer(
        string="Avec code-barres",
        compute='_compute_counts',
    )
    
    count_without_barcode = fields.Integer(
        string="Sans code-barres",
        compute='_compute_counts',
    )
    
    has_products_with_barcode = fields.Boolean(
        string="Contient des produits avec code-barres",
        compute='_compute_counts',
    )
    
    regenerate_existing = fields.Boolean(
        string="Régénérer les codes-barres existants",
        default=False,
        help="Si coché, les produits ayant déjà un code-barres recevront "
             "un nouveau code-barres. Sinon, seuls les produits sans "
             "code-barres seront traités.",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('product_ids')
    def _compute_counts(self):
        """Compute product counts with and without barcodes."""
        for wizard in self:
            products = wizard.product_ids
            with_barcode = products.filtered(lambda p: p.barcode)
            without_barcode = products.filtered(lambda p: not p.barcode)
            
            wizard.count_total = len(products)
            wizard.count_with_barcode = len(with_barcode)
            wizard.count_without_barcode = len(without_barcode)
            wizard.has_products_with_barcode = bool(with_barcode)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def _generate_barcode(self):
        """Generate a unique random 10-digit barcode.
        
        Returns a string of 10 random digits, ensuring uniqueness
        by checking against existing barcodes in the database.
        """
        ProductProduct = self.env['product.product']
        max_attempts = 100
        for _ in range(max_attempts):
            # Generate random 10-digit number (1000000000 to 9999999999)
            barcode = str(random.randint(1000000000, 9999999999))
            # Check if barcode already exists
            existing = ProductProduct.sudo().search_count([('barcode', '=', barcode)])
            if existing == 0:
                return barcode
        # Fallback: if we couldn't generate unique after max_attempts
        # use timestamp-based generation
        return str(int(time.time() * 1000))[-10:]

    def action_confirm(self):
        """Confirm and assign barcodes to selected products."""
        self.ensure_one()
        
        if self.regenerate_existing:
            # Assign barcodes to ALL products (including those with existing barcodes)
            products_to_update = self.product_ids
        else:
            # Only assign to products without barcodes
            products_to_update = self.product_ids.filtered(lambda p: not p.barcode)
        
        for product in products_to_update:
            product.barcode = self._generate_barcode()
        
        # Close wizard and show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Codes-barres assignés',
                'message': f'{len(products_to_update)} produit(s) ont reçu un code-barres.',
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_cancel(self):
        """Cancel the wizard."""
        return {'type': 'ir.actions.act_window_close'}
