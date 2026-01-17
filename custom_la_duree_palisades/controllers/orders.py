# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Override self-order controller to use custom preset configuration.

This module fixes the preset validation issue where the native controller
uses `use_presets` field but we have a separate `self_order_use_presets`
field for self-order specific configuration.
"""

from odoo import fields
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController
from odoo.http import request
from werkzeug.exceptions import BadRequest, Unauthorized


class PosSelfOrderControllerInherit(PosSelfOrderController):
    """Override process_order to use custom self_order_use_presets field."""

    def _verify_authorization(self, access_token, table_identifier, order):
        """Override to use self_order_use_presets instead of use_presets.
        
        The native method uses `pos_config.use_presets` to determine if the order
        is takeaway, but our custom module uses a separate `self_order_use_presets` 
        field for self-order configuration.
        """
        pos_config = self._verify_pos_config(access_token)
        table_sudo = request.env["restaurant.table"].sudo().search([('identifier', '=', table_identifier)], limit=1)
        preset = request.env['pos.preset'].sudo().browse(order.get('preset_id'))
        
        # Use custom self_order_use_presets field instead of native use_presets
        is_takeaway = order and pos_config.self_order_use_presets and preset and preset.service_at != 'table'
        
        if not table_sudo and pos_config.self_ordering_mode != 'kiosk' and pos_config.self_ordering_service_mode == 'table' and not is_takeaway:
            raise Unauthorized("Table not found")

        company = pos_config.company_id
        user = pos_config.self_ordering_default_user_id
        table = table_sudo.sudo(False).with_company(company).with_user(user).with_context(allowed_company_ids=company.ids)
        return pos_config, table

    def process_order(self, order, access_token, table_identifier, device_type):
        """Override to use self_order_use_presets instead of use_presets.
        
        The native controller checks `pos_config.use_presets` for preset validation,
        but our custom module uses a separate `self_order_use_presets` field for
        self-order configuration. This override ensures the correct field is used.
        """
        pos_config, table = self._verify_authorization(access_token, table_identifier, order)
        
        # Use custom self_order_use_presets field instead of native use_presets
        use_self_order_presets = pos_config.self_order_use_presets
        
        preset_id = order.get('preset_id') if use_self_order_presets else False
        preset_id = pos_config.env['pos.preset'].browse(preset_id) if preset_id else False

        if not preset_id and use_self_order_presets:
            raise BadRequest("Invalid preset")

        # Continue with order processing
        return self._process_order_with_preset(pos_config, table, order, preset_id, device_type, use_self_order_presets)
    
    def _process_order_with_preset(self, pos_config, table, order, preset_id, device_type, use_presets):
        """Process the order with the validated preset.
        
        This is extracted from the native controller to avoid double validation.
        """
        # Create the order
        if 'picking_type_id' in order:
            del order['picking_type_id']

        if 'name' in order:
            del order['name']

        pos_reference, tracking_number = pos_config._get_next_order_refs()
        if device_type == 'kiosk':
            order['floating_order_name'] = f"Table tracker {order['table_stand_number']}" if order.get('table_stand_number') else tracking_number

        if not order.get('floating_order_name') and table:
            floating_order_name = f"Self-order T {table.table_number}"
        elif not order.get('floating_order_name'):
            floating_order_name = f"Self-order {tracking_number}"
        else:
            floating_order_name = order.get('floating_order_name')

        prefix = 'K' if device_type == 'kiosk' else 'S'
        order['pos_reference'] = pos_reference
        order['source'] = 'kiosk' if device_type == 'kiosk' else 'mobile'
        order['floating_order_name'] = floating_order_name
        order['tracking_number'] = f"{prefix}{tracking_number}"
        order['user_id'] = request.session.uid
        order['date_order'] = str(fields.Datetime.now())
        order['fiscal_position_id'] = preset_id.fiscal_position_id.id if preset_id else pos_config.default_fiscal_position_id.id
        order['pricelist_id'] = preset_id.pricelist_id.id if preset_id else pos_config.pricelist_id.id
        order['self_ordering_table_id'] = table.id if table else False

        results = pos_config.env['pos.order'].sudo().with_company(pos_config.company_id.id).sync_from_ui([order])
        line_ids = pos_config.env['pos.order.line'].browse([line['id'] for line in results['pos.order.line']])
        order_ids = pos_config.env['pos.order'].browse([order['id'] for order in results['pos.order']])

        self._verify_line_price(line_ids, pos_config, preset_id)

        amount_total, amount_untaxed = self._get_order_prices(order_ids.lines)
        order_ids.write({
            'state': 'paid' if amount_total == 0 else 'draft',
            'amount_tax': amount_total - amount_untaxed,
            'amount_total': amount_total,
        })

        if amount_total == 0:
            order_ids._process_saved_order(False)

        return self._generate_return_values(order_ids, pos_config)

