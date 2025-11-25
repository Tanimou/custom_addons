from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time
import re
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'


    helpdesk_id = fields.Many2one(
        'helpdesk.ticket',
        string="Ticket Helpdesk"
    )

    def create(self, vals_list):
        """
        Lors de la création d'un achat, l'ajouter automatiquement au ticket
        """
        orders = super(PurchaseOrderInherit, self).create(vals_list)
        
        for order in orders:
            if order.helpdesk_id:
                if order.id not in order.helpdesk_id.purchase_ids.ids:
                    order.helpdesk_id.write({
                        'purchase_ids': [(4, order.id)]
                    })     
        return orders
    
    
    def write(self, vals):
        """
        Lors de la modification, gérer l'ajout/retrait du ticket
        """
        res = super(PurchaseOrderInherit, self).write(vals)
        
        # Si le helpdesk_id a changé
        if 'helpdesk_id' in vals:
            for order in self:
                new_ticket_id = vals.get('helpdesk_id')
                if new_ticket_id:
                    new_ticket = self.env['helpdesk.ticket'].browse(new_ticket_id)
                    if order.id not in new_ticket.purchase_ids.ids:
                        new_ticket.write({
                            'purchase_ids': [(4, order.id)]
                        })       
        return res