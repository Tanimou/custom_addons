# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_bon_achat_info_line = fields.Boolean(
        string="Bon d'achat info line",
        help="Marks POS reward lines that should only display Bon d'achat information without affecting totals.",
    )
    bon_achat_applied_amount = fields.Monetary(
        string="Bon d'achat applied",
        currency_field='currency_id',
        help="Amount effectively covered by the Bon d'achat on this order line.",
    )
    bon_achat_original_amount = fields.Monetary(
        string="Bon d'achat original",
        currency_field='currency_id',
        help="Original value of the Bon d'achat at the moment of usage.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        """
        Override to include bon_achat fields in POS data loading.
        These fields are needed by the frontend to detect and sum voucher amounts.
        """
        fields = super()._load_pos_data_fields(config)
        fields.extend(['is_bon_achat_info_line', 'bon_achat_applied_amount', 'bon_achat_original_amount'])
        return fields

    @api.model_create_multi
    def create(self, vals_list):
        reward_model = self.env['loyalty.reward']
        processed_vals = []
        for vals in vals_list:
            vals = dict(vals)
            if self._is_bon_achat_reward_line(vals, reward_model):
                self._prepare_bon_achat_info_vals(vals)
            processed_vals.append(vals)
        return super().create(processed_vals)

    def _is_bon_achat_reward_line(self, vals, reward_model):
        reward_id = vals.get('reward_id')
        if not reward_id:
            return False
        reward = reward_model.browse(reward_id)
        return bool(reward and reward.program_id.program_type == 'bon_achat')

    def _prepare_bon_achat_info_vals(self, vals):
        applied_amount = vals.get('bon_achat_applied_amount')
        if applied_amount is None:
            applied_amount = abs(vals.get('price_subtotal_incl') or vals.get('price_subtotal') or 0.0)
        vals.setdefault('customer_note', vals.get('customer_note') or _("Bon d'achat"))
        vals['is_bon_achat_info_line'] = True
        vals['bon_achat_applied_amount'] = applied_amount
        vals.setdefault('bon_achat_original_amount', applied_amount)
        # Neutralize amounts so backend totals are not impacted; the applied amount is kept in metadata
        vals['price_unit'] = 0.0
        vals['price_subtotal'] = 0.0
        vals['price_subtotal_incl'] = 0.0
        vals['discount'] = 0.0
