from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_open_wizard(self):
        return {
            'name': "Ajouter produits",
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.multi.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_id': self.id,
            }
        }

    