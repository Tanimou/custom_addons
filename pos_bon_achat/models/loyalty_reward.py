# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    @api.onchange('program_id')
    def _onchange_program_id_per_product(self):
        """
        When program has buy_x_get_y with per_product_mode enabled,
        automatically populate reward_product_ids with the conditional products
        from the rules, since each product rewards itself.
        """
        self._auto_populate_reward_products()

    @api.onchange('reward_type')
    def _onchange_reward_type_per_product(self):
        """Auto-populate reward products when reward_type changes to product"""
        if self.reward_type == 'product':
            self._auto_populate_reward_products()

    def _auto_populate_reward_products(self):
        """Helper method to auto-populate reward products for per_product_mode programs"""
        if not self.program_id or self.program_id.program_type != 'buy_x_get_y':
            return

        # Check if any rule has per_product_mode enabled
        has_per_product_mode = any(
            rule.per_product_mode for rule in self.program_id.rule_ids
        )

        if has_per_product_mode and self.reward_type == 'product':
            # Collect all valid products from rules with per_product_mode
            valid_products = self.env['product.product']
            for rule in self.program_id.rule_ids:
                if rule.per_product_mode and rule.valid_product_ids:
                    valid_products |= rule.valid_product_ids

            if valid_products:
                # Auto-populate reward products with conditional products
                self.reward_product_ids = valid_products

