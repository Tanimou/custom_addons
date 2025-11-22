# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class PurchaseOrder(models.Model):
    """Extend purchase.order - Phase 4: Restrict purchases to approved suppliers"""
    _inherit = 'purchase.order'

    def button_confirm(self):
        """Override confirmation to block orders from non-approved suppliers"""
        from odoo.exceptions import UserError
        
        for order in self:
            if order.partner_id and not order.partner_id.supplier_approved:
                raise UserError(
                    _('Cannot confirm purchase order %s!\n\n'
                      'Supplier "%s" must be approved before creating purchase orders.\n'
                      'Please submit an approval request first.') % 
                    (order.name, order.partner_id.name)
                )
        
        return super().button_confirm()
