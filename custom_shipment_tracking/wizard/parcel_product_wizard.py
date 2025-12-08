# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ParcelProductWizard(models.TransientModel):
    """Wizard to add/view products in a parcel from linked sale orders."""

    _name = 'parcel.product.wizard'
    _description = 'Assistant de sélection des produits du colis'

    # region Fields
    parcel_id = fields.Many2one(
        comodel_name='shipment.parcel',
        string='Colis',
        required=True,
        readonly=True,
    )
    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande d\'expédition',
        readonly=True,
    )
    shipment_state = fields.Selection(
        related='shipment_request_id.state',
        string='État de la demande',
        readonly=True,
    )
    is_readonly = fields.Boolean(
        string='Mode lecture seule',
        compute='_compute_is_readonly',
    )
    
    # Available products from sale orders - populated in default_get
    available_line_ids = fields.One2many(
        comodel_name='parcel.product.wizard.line',
        inverse_name='wizard_id',
        string='Produits disponibles',
    )
    
    # Summary fields
    parcel_name = fields.Char(
        string='Référence du colis',
        readonly=True,
    )
    total_products = fields.Integer(
        string='Nombre de produits',
        compute='_compute_totals',
    )
    total_value = fields.Monetary(
        string='Valeur totale',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        related='parcel_id.currency_id',
    )
    # endregion

    # region Default Get
    @api.model
    def default_get(self, fields_list):
        """Populate available_line_ids from parcel context."""
        res = super().default_get(fields_list)
        
        parcel_id = res.get('parcel_id') or self.env.context.get('default_parcel_id')
        if not parcel_id:
            return res
        
        parcel = self.env['shipment.parcel'].browse(parcel_id)
        if not parcel.exists():
            return res
        
        # Set parcel name explicitly (related fields don't work well in default_get)
        res['parcel_name'] = parcel.name or parcel.display_name
        
        shipment = parcel.shipment_request_id
        res['shipment_request_id'] = shipment.id
        
        if not shipment.sale_order_ids:
            return res
        
        # Get all sale order lines from linked orders (physical products only)
        order_lines = shipment.sale_order_ids.mapped('order_line').filtered(
            lambda l: l.product_id and l.product_id.type in ('product', 'consu')
        )
        
        if not order_lines:
            return res
        
        # Get existing parcel lines for this parcel to determine is_selected and selected_qty
        ParcelLine = self.env['shipment.parcel.line']
        existing_lines = ParcelLine.search([
            ('parcel_id', '=', parcel.id),
        ])
        existing_by_sol = {l.sale_order_line_id.id: l for l in existing_lines}
        
        lines_vals = []
        for sol in order_lines:
            # Calculate quantity already assigned to OTHER parcels in this shipment
            all_assigned = ParcelLine.search([
                ('sale_order_line_id', '=', sol.id),
                ('parcel_id.shipment_request_id', '=', shipment.id),
                ('parcel_id', '!=', parcel.id),  # Exclude current parcel
            ])
            assigned_to_others = sum(all_assigned.mapped('quantity'))
            
            # Quantity in current parcel
            current_parcel_line = existing_by_sol.get(sol.id)
            qty_in_current = current_parcel_line.quantity if current_parcel_line else 0.0
            
            # Remaining = ordered - assigned to others (NOT including current parcel)
            remaining_qty = sol.product_uom_qty - assigned_to_others
            
            # For new parcels, only show products with remaining qty > 0
            # For existing entries in this parcel, always show them
            if remaining_qty <= 0 and qty_in_current <= 0:
                continue  # Skip products with no availability
            
            # Only set the fields that need defaults (is_selected, selected_qty)
            # Other fields (product_id, order_qty, unit_price, etc.) are related/computed
            lines_vals.append((0, 0, {
                'sale_order_line_id': sol.id,
                'selected_qty': qty_in_current,  # Default to current value in parcel
                'is_selected': bool(current_parcel_line),
            }))
        
        res['available_line_ids'] = lines_vals
        return res
    # endregion

    # region Computed Fields
    @api.depends('shipment_state')
    def _compute_is_readonly(self):
        """Determine if wizard should be in readonly mode."""
        for wizard in self:
            # Check context for explicit readonly mode
            readonly_mode = self.env.context.get('readonly_mode', False)
            # Allow editing in 'registered' and 'grouping' states
            editable_states = ('registered', 'grouping')
            wizard.is_readonly = readonly_mode or wizard.shipment_state not in editable_states

    @api.depends('available_line_ids.selected_qty', 'available_line_ids.is_selected')
    def _compute_totals(self):
        """Compute total selected products and value."""
        for wizard in self:
            selected_lines = wizard.available_line_ids.filtered('is_selected')
            wizard.total_products = len(selected_lines)
            wizard.total_value = sum(
                line.selected_qty * line.unit_price 
                for line in selected_lines
            )
    # endregion

    # region Actions
    def action_confirm(self):
        """Confirm product selection and update parcel lines."""
        self.ensure_one()
        
        if self.is_readonly:
            # In readonly mode, just close the wizard
            return {'type': 'ir.actions.act_window_close'}
        
        ParcelLine = self.env['shipment.parcel.line']
        
        # Get existing parcel lines for this parcel
        existing_lines = ParcelLine.search([
            ('parcel_id', '=', self.parcel_id.id),
        ])
        existing_by_sol = {l.sale_order_line_id.id: l for l in existing_lines}
        
        lines_to_create = []
        lines_to_delete = ParcelLine
        
        for wiz_line in self.available_line_ids:
            sol_id = wiz_line.sale_order_line_id.id
            existing_line = existing_by_sol.get(sol_id)
            
            if wiz_line.is_selected and wiz_line.selected_qty > 0:
                # Validate quantity - can't exceed remaining qty
                max_allowed = wiz_line.remaining_qty
                if wiz_line.selected_qty > max_allowed:
                    raise ValidationError(_(
                        'La quantité sélectionnée pour "%s" (%s) dépasse la quantité disponible (%s).'
                    ) % (
                        wiz_line.product_id.name,
                        wiz_line.selected_qty,
                        max_allowed,
                    ))
                
                if existing_line:
                    # Update existing line
                    if existing_line.quantity != wiz_line.selected_qty:
                        existing_line.write({'quantity': wiz_line.selected_qty})
                        _logger.info(
                            'Updated parcel line %s: qty = %s',
                            wiz_line.product_id.name,
                            wiz_line.selected_qty,
                        )
                else:
                    # Create new line
                    lines_to_create.append({
                        'parcel_id': self.parcel_id.id,
                        'sale_order_line_id': sol_id,
                        'quantity': wiz_line.selected_qty,
                    })
            else:
                # Not selected or zero quantity - delete if exists
                if existing_line:
                    lines_to_delete |= existing_line
        
        # Apply changes
        if lines_to_delete:
            lines_to_delete.unlink()
            _logger.info(
                'Deleted %d parcel lines from parcel %s',
                len(lines_to_delete),
                self.parcel_id.name,
            )
        
        if lines_to_create:
            ParcelLine.create(lines_to_create)
            _logger.info(
                'Created %d parcel lines for parcel %s',
                len(lines_to_create),
                self.parcel_id.name,
            )
        
        return {'type': 'ir.actions.act_window_close'}

    def action_select_all(self):
        """Select all available products with remaining quantity."""
        self.ensure_one()
        for line in self.available_line_ids:
            if line.remaining_qty > 0:
                line.is_selected = True
                line.selected_qty = line.remaining_qty
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_clear_all(self):
        """Clear all selections."""
        self.ensure_one()
        for line in self.available_line_ids:
            line.is_selected = False
            line.selected_qty = 0
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    # endregion


class ParcelProductWizardLine(models.TransientModel):
    """Line model for parcel product selection wizard."""

    _name = 'parcel.product.wizard.line'
    _description = 'Ligne de sélection de produit pour colis'

    # region Fields
    wizard_id = fields.Many2one(
        comodel_name='parcel.product.wizard',
        string='Assistant',
        required=True,
        ondelete='cascade',
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Ligne de commande',
        required=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Produit',
        related='sale_order_line_id.product_id',
        readonly=True,
    )
    sale_order_name = fields.Char(
        string='Commande',
        related='sale_order_line_id.order_id.name',
        readonly=True,
    )
    
    # Quantities - computed from sale_order_line_id to ensure they always have values
    order_qty = fields.Float(
        string='Qté commandée',
        related='sale_order_line_id.product_uom_qty',
        readonly=True,
        digits='Product Unit of Measure',
    )
    assigned_to_others = fields.Float(
        string='Qté autres colis',
        compute='_compute_quantities',
        digits='Product Unit of Measure',
        help='Quantité déjà affectée à d\'autres colis dans cette expédition',
    )
    remaining_qty = fields.Float(
        string='Qté disponible',
        compute='_compute_quantities',
        digits='Product Unit of Measure',
        help='Quantité restante disponible pour ce colis',
    )
    qty_in_parcel = fields.Float(
        string='Qté actuelle',
        compute='_compute_quantities',
        digits='Product Unit of Measure',
        help='Quantité actuellement enregistrée dans ce colis',
    )
    
    # Selection
    is_selected = fields.Boolean(
        string='Sélectionné',
        default=False,
    )
    selected_qty = fields.Float(
        string='Quantité',
        digits='Product Unit of Measure',
        default=0.0,
    )
    
    # Price - computed from sale_order_line_id
    unit_price = fields.Float(
        string='Prix unitaire',
        related='sale_order_line_id.price_unit',
        readonly=True,
    )
    subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_subtotal',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='wizard_id.currency_id',
    )
    # endregion

    # region Computed Fields
    @api.depends('sale_order_line_id', 'wizard_id.parcel_id', 'wizard_id.shipment_request_id')
    def _compute_quantities(self):
        """Compute quantities dynamically from sale order line and parcel context."""
        ParcelLine = self.env['shipment.parcel.line']
        
        for line in self:
            if not line.sale_order_line_id or not line.wizard_id.parcel_id:
                line.assigned_to_others = 0.0
                line.remaining_qty = 0.0
                line.qty_in_parcel = 0.0
                continue
            
            sol = line.sale_order_line_id
            parcel = line.wizard_id.parcel_id
            shipment = line.wizard_id.shipment_request_id
            
            # Quantity assigned to OTHER parcels in this shipment
            other_parcel_lines = ParcelLine.search([
                ('sale_order_line_id', '=', sol.id),
                ('parcel_id.shipment_request_id', '=', shipment.id),
                ('parcel_id', '!=', parcel.id),  # Exclude current parcel
            ])
            line.assigned_to_others = sum(other_parcel_lines.mapped('quantity'))
            
            # Quantity already in current parcel
            current_parcel_line = ParcelLine.search([
                ('sale_order_line_id', '=', sol.id),
                ('parcel_id', '=', parcel.id),
            ], limit=1)
            line.qty_in_parcel = current_parcel_line.quantity if current_parcel_line else 0.0
            
            # Remaining = ordered - assigned to others (NOT including current parcel)
            line.remaining_qty = sol.product_uom_qty - line.assigned_to_others

    @api.depends('selected_qty', 'unit_price')
    def _compute_subtotal(self):
        """Compute subtotal based on selected quantity and unit price."""
        for line in self:
            line.subtotal = line.selected_qty * line.unit_price
    # endregion

    # region Onchange
    @api.onchange('is_selected')
    def _onchange_is_selected(self):
        """When selection changes, set default quantity."""
        if self.is_selected:
            # Default to remaining qty (what's available for this parcel)
            self.selected_qty = self.remaining_qty
        else:
            self.selected_qty = 0.0

    @api.onchange('selected_qty')
    def _onchange_selected_qty(self):
        """Auto-select when quantity is entered."""
        if self.selected_qty > 0:
            self.is_selected = True
        elif self.selected_qty <= 0:
            self.is_selected = False
            self.selected_qty = 0.0
    # endregion
