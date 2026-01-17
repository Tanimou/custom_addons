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

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """Override to map self-order preset fields to native preset fields.
        
        The frontend JavaScript uses `config.use_presets`, `config.default_preset_id`,
        and `config.available_preset_ids` to determine preset behavior. However, our
        custom module uses separate self-order specific fields.
        
        This override maps the custom self-order fields to the native fields when
        loading data for the self-order interface, so the frontend sees the correct
        configuration without needing JavaScript modifications.
        
        Args:
            records: The pos.config records to read
            config: The pos.config record for which data is being loaded
            
        Returns:
            list: The read records with self-order preset fields mapped to native fields
        """
        result = super()._load_pos_self_data_read(records, config)
        
        if not result:
            return result
        
        # Map self-order preset configuration to native fields for frontend
        # This makes the frontend see the self-order specific configuration
        for record in result:
            if config.self_order_use_presets:
                # Override native preset fields with self-order specific values
                record['use_presets'] = config.self_order_use_presets
                record['default_preset_id'] = config.self_order_default_preset_id.id if config.self_order_default_preset_id else False
                record['available_preset_ids'] = config.self_order_available_preset_ids.ids if config.self_order_available_preset_ids else []
        
        return result
