from odoo import models, fields, _, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ProductSelectWizard(models.TransientModel):
    _name = 'stock.picking.multi.product.wizard'
    _description = 'Sélection multiple de produits'

    product_ids = fields.Many2many('product.product', string="Produits")
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        string='Recevoir de',
        help="Société à laquelle appartient le transfert inter-société")

    def action_add_products(self):
        active_id = self.env.context.get('active_id')
        picking_id = self.env['stock.picking'].browse(active_id)
        for product in self.product_ids:
            self.env['stock.move'].create({
                'picking_id': picking_id.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
            })
