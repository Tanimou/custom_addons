# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Extend res.config.settings with self-order preset configuration.
    
    These related fields expose the self-order preset settings in the
    Point of Sale configuration UI, allowing users to configure separate
    preset settings for regular POS and self-order interfaces.
    """
    _inherit = 'res.config.settings'

    # Self-Order Preset Settings - exposed in the POS settings view
    pos_self_order_use_presets = fields.Boolean(
        related='pos_config_id.self_order_use_presets',
        readonly=False,
        string="Utiliser des Préréglages (Self-Order)",
    )
    
    pos_self_order_default_preset_id = fields.Many2one(
        related='pos_config_id.self_order_default_preset_id',
        readonly=False,
        string="Préréglage par défaut (Self-Order)",
    )
    
    pos_self_order_available_preset_ids = fields.Many2many(
        related='pos_config_id.self_order_available_preset_ids',
        readonly=False,
        string="Préréglages disponibles (Self-Order)",
    )
