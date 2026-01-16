# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosPreset(models.Model):
    """Extend pos.preset to use separate self-order preset configuration.
    
    This overrides the `_load_pos_self_data_domain` method to use the new
    self-order specific preset fields instead of the shared regular POS fields.
    """
    _inherit = 'pos.preset'

    def _load_pos_self_data_domain(self, data, config):
        """Override to use self-order specific preset configuration.
        
        When the POS config has `self_order_use_presets` enabled, it uses
        the self-order specific fields. Otherwise, falls back to the native
        behavior for backward compatibility.
        
        Args:
            data: The data dictionary being loaded for the self-order interface
            config: The pos.config record for which data is being loaded
            
        Returns:
            list: Domain filter for loading presets appropriate for self-order
        """
        # Check if custom self-order preset configuration is enabled
        if config.self_order_use_presets:
            # Use the separate self-order preset configuration
            return [
                '|',
                ('id', '=', config.self_order_default_preset_id.id),
                '&',
                ('available_in_self', '=', True),
                ('id', 'in', config.self_order_available_preset_ids.ids),
            ]
        else:
            # Fall back to native behavior (uses regular POS preset fields)
            # This maintains backward compatibility when self_order_use_presets is False
            return super()._load_pos_self_data_domain(data, config)
