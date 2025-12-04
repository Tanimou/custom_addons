# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Extension du modèle product.product pour lier les produits aux immobilisations.

Ce module ajoute une relation entre les produits (équipements physiques)
et les immobilisations comptables (account.asset) pour permettre:
- La traçabilité physique des équipements amortissables
- Le lien entre inventaire physique et valorisation comptable
"""

import random

from odoo import api, fields, models


class ProductProduct(models.Model):
    """Extension de product.product pour le lien avec les immobilisations."""

    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string="Immobilisation liée",
        domain="[('company_id', '=', company_id), ('state', 'not in', ['model', 'cancelled'])]",
        copy=False,
        tracking=True,
        help="Immobilisation comptable associée à ce produit pour le suivi "
             "des amortissements et la valorisation d'inventaire.",
    )
    
    has_asset = fields.Boolean(
        string="A une immobilisation",
        compute='_compute_has_asset',
        store=True,
        help="Indique si ce produit est lié à une immobilisation comptable",
    )
    
    # Champs related depuis l'immobilisation pour affichage rapide
    asset_book_value = fields.Monetary(
        string="Valeur nette comptable",
        related='asset_id.book_value',
        readonly=True,
        currency_field='currency_id',
    )
    asset_state = fields.Selection(
        related='asset_id.state',
        string="État immobilisation",
        readonly=True,
    )
    asset_acquisition_date = fields.Date(
        related='asset_id.acquisition_date',
        string="Date d'acquisition",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('asset_id')
    def _compute_has_asset(self):
        """Calcule si le produit a une immobilisation liée."""
        for product in self:
            product.has_asset = bool(product.asset_id)

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate barcode if not provided."""
        for vals in vals_list:
            if not vals.get('barcode'):
                vals['barcode'] = self._generate_barcode()
        return super().create(vals_list)

    def _generate_barcode(self):
        """Generate a unique random 10-digit barcode.
        
        Returns a string of 10 random digits, ensuring uniqueness
        by checking against existing barcodes in the database.
        """
        max_attempts = 100
        for _ in range(max_attempts):
            # Generate random 10-digit number (1000000000 to 9999999999)
            barcode = str(random.randint(1000000000, 9999999999))
            # Check if barcode already exists
            existing = self.sudo().search_count([('barcode', '=', barcode)])
            if existing == 0:
                return barcode
        # Fallback: if we couldn't generate unique after max_attempts
        # use timestamp-based generation
        import time
        return str(int(time.time() * 1000))[-10:]

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_assign_barcode(self):
        """Assign barcode to products that don't have one (bulk action)."""
        products_without_barcode = self.filtered(lambda p: not p.barcode)
        for product in products_without_barcode:
            product.barcode = self._generate_barcode()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Barcodes assignés',
                'message': f'{len(products_without_barcode)} produit(s) ont reçu un code-barres.',
                'sticky': False,
                'type': 'success',
            }
        }

    def action_view_asset(self):
        """Open the linked asset form view."""
        self.ensure_one()
        if not self.asset_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.asset_id.name,
            'res_model': 'account.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ProductTemplate(models.Model):
    """Extension de product.template pour exposer les champs asset."""

    _inherit = 'product.template'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    # Exposer les champs asset au niveau du template pour les vues
    # Note: Use compute/inverse for single-variant templates
    variant_asset_id = fields.Many2one(
        comodel_name='account.asset',
        string="Immobilisation liée",
        compute='_compute_variant_asset_id',
        inverse='_inverse_variant_asset_id',
        help="Immobilisation comptable associée à ce produit",
    )
    
    has_asset = fields.Boolean(
        string="A une immobilisation",
        compute='_compute_has_asset',
        store=True,
    )
    
    variant_asset_book_value = fields.Monetary(
        string="Valeur nette comptable",
        compute='_compute_variant_asset_id',
        currency_field='currency_id',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('product_variant_ids', 'product_variant_ids.asset_id', 'product_variant_ids.asset_book_value')
    def _compute_variant_asset_id(self):
        """Get the asset from the single variant."""
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.variant_asset_id = template.product_variant_ids.asset_id
                template.variant_asset_book_value = template.product_variant_ids.asset_book_value
            else:
                template.variant_asset_id = False
                template.variant_asset_book_value = 0.0

    def _inverse_variant_asset_id(self):
        """Set the asset on the single variant."""
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.asset_id = template.variant_asset_id

    @api.depends('product_variant_ids.has_asset')
    def _compute_has_asset(self):
        """Calcule si le template a au moins un variant avec immobilisation."""
        for template in self:
            template.has_asset = any(
                variant.has_asset for variant in template.product_variant_ids
            )

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def action_view_asset(self):
        """Open the linked asset form view."""
        self.ensure_one()
        if len(self.product_variant_ids) == 1 and self.product_variant_ids.asset_id:
            return self.product_variant_ids.action_view_asset()
        return False

    def action_assign_barcode(self):
        """Assign barcode to product variants that don't have one (bulk action)."""
        # Get all variants from selected templates
        variants = self.mapped('product_variant_ids')
        variants_without_barcode = variants.filtered(lambda p: not p.barcode)
        for variant in variants_without_barcode:
            variant.barcode = variant._generate_barcode()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Codes-barres assignés',
                'message': f'{len(variants_without_barcode)} produit(s) ont reçu un code-barres.',
                'sticky': False,
                'type': 'success',
            }
        }
