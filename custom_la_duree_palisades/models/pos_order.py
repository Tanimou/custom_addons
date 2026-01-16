# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Simple informative field for pickup status - no compute, just selection
    # Persists in database so it survives POS reload within session
    pickup_status = fields.Selection([
        ('waiting', 'En attente de retrait'),
        ('picked_up', 'Retiré'),
    ], string='Statut retrait', default='waiting', 
       help="Statut de retrait pour les commandes self-order")
