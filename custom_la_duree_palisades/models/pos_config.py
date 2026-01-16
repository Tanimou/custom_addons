# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    """Extend pos.config to add separate preset configuration for self-order.
    
    This allows the regular POS and the autonomous mobile/kiosk version
    to have independent preset settings instead of sharing the same configuration.
    """
    _inherit = 'pos.config'

    # Self-Order Preset Settings (separate from regular POS presets)
    self_order_use_presets = fields.Boolean(
        string="Utiliser des Préréglages (Self-Order)",
        help="Enable preset functionality for the self-ordering kiosk/mobile interface. "
             "When enabled, customers can select from available presets on the self-order screen.",
        default=False,
    )
    
    self_order_default_preset_id = fields.Many2one(
        'pos.preset',
        string='Préréglage par défaut (Self-Order)',
        help="The default preset to apply when a customer starts a new order on the self-order interface. "
             "This preset will be pre-selected when the self-order screen opens.",
    )
    
    self_order_available_preset_ids = fields.Many2many(
        'pos.preset',
        'pos_config_self_order_preset_rel',  # Explicit relation table name
        'pos_config_id',
        'pos_preset_id',
        string='Préréglages disponibles (Self-Order)',
        help="The list of presets available for selection on the self-order interface. "
             "Only these presets will be shown to customers on the kiosk/mobile screen.",
    )

    @api.constrains('self_order_default_preset_id', 'self_order_available_preset_ids')
    def _check_self_order_default_in_available(self):
        """Ensure the default preset is in the available presets list."""
        for config in self:
            if config.self_order_default_preset_id and config.self_order_available_preset_ids:
                if config.self_order_default_preset_id not in config.self_order_available_preset_ids:
                    raise ValidationError(_(
                        "Le préréglage par défaut Self-Order '%s' doit être inclus dans la "
                        "liste des préréglages disponibles Self-Order.",
                        config.self_order_default_preset_id.name
                    ))
