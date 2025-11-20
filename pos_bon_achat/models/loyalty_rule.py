# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    per_product_mode = fields.Boolean(
        string="Apply Per Product Line",
        default=False,
        help="When enabled, the minimum quantity requirement is checked separately for each "
             "order line instead of across the entire order. This allows 'Buy X Get Y' programs "
             "to apply per-product rather than per-order. Only applicable when reward_point_mode='unit' "
             "and program applies_on='current'."
    )

    @api.model
    def _load_pos_data_fields(self, config):
        """Ensure per_product_mode field is loaded in POS frontend"""
        fields = super()._load_pos_data_fields(config)
        # Ensure we return a list (not append to return value directly)
        if not isinstance(fields, list):
            fields = list(fields)
        if 'per_product_mode' not in fields:
            fields.append('per_product_mode')
        return fields
