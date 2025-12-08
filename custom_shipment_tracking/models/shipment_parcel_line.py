# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShipmentParcelLine(models.Model):
    """Ligne de colis - Product line within a parcel."""

    _name = 'shipment.parcel.line'
    _description = 'Ligne de colis'
    _order = 'parcel_id, sequence, id'

    # region Fields
    parcel_id = fields.Many2one(
        comodel_name='shipment.parcel',
        string='Colis',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Séquence',
        default=10,
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Ligne de commande',
        required=True,
        ondelete='restrict',
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Produit',
        related='sale_order_line_id.product_id',
        store=True,
        readonly=True,
    )
    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Modèle de produit',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True,
    )
    product_name = fields.Char(
        string='Description',
        compute='_compute_product_name',
        store=True,
    )
    quantity = fields.Float(
        string='Quantité',
        required=True,
        default=1.0,
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unité de mesure',
        related='sale_order_line_id.product_uom_id',
        store=True,
        readonly=True,
    )
    unit_price = fields.Float(
        string='Prix unitaire',
        related='sale_order_line_id.price_unit',
        readonly=True,
    )
    ordered_qty = fields.Float(
        string='Qté commandée',
        related='sale_order_line_id.product_uom_qty',
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        related='sale_order_line_id.currency_id',
        readonly=True,
    )
    subtotal = fields.Monetary(
        string='Sous-total',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )

    # Related shipment info
    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande d\'expédition',
        related='parcel_id.shipment_request_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        related='parcel_id.partner_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        related='parcel_id.company_id',
        store=True,
        readonly=True,
    )
    # endregion

    # region Computes
    @api.depends('sale_order_line_id', 'sale_order_line_id.name', 'product_id.display_name')
    def _compute_product_name(self):
        for line in self:
            if line.sale_order_line_id:
                line.product_name = line.sale_order_line_id.name or line.product_id.display_name
            else:
                line.product_name = ''

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
    # endregion

    # region Constraints
    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(
                    'La quantité doit être supérieure à zéro.'
                )

    @api.constrains('quantity', 'ordered_qty')
    def _check_quantity_not_exceed(self):
        """Warn if quantity exceeds ordered quantity (but don't block)."""
        for line in self:
            if line.quantity > line.ordered_qty:
                _logger.warning(
                    'Parcel line %s has quantity %s exceeding ordered qty %s',
                    line.id,
                    line.quantity,
                    line.ordered_qty,
                )
    # endregion

    # region Name Get
    def name_get(self):
        result = []
        for line in self:
            name = f'{line.product_id.display_name} ({line.quantity} {line.product_uom_id.name})'
            result.append((line.id, name))
        return result
    # endregion
