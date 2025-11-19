# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# pyright: reportAttributeAccessIssue=false, reportGeneralTypeIssues=false

from copy import deepcopy

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round


class PosOrder(models.Model):
    _inherit = 'pos.order'

    bon_achat_applied_total = fields.Monetary(
        string="Bon d'achat applied total",
        currency_field='currency_id',
        help="Total amount covered by Bon d'achat vouchers on this order.",
    )

    def validate_coupon_programs(self, point_changes, new_codes):
        """
        Override to add bon_achat specific validation.
        Check that bon_achat coupons are still valid (not already used).
        """
        # Call parent validation first
        result = super().validate_coupon_programs(point_changes, new_codes)
        
        if not result.get('successful'):
            return result
        
        # Additional validation for bon_achat coupons
        point_changes = {int(k): v for k, v in point_changes.items()}
        coupon_ids = list(point_changes.keys())
        
        # Get bon_achat coupons being used
        bon_achat_coupons = self.env['loyalty.card'].browse(coupon_ids).filtered(
            lambda c: c.program_type == 'bon_achat'
        )
        
        # Validate each bon_achat coupon
        for coupon in bon_achat_coupons:
            try:
                coupon._check_bon_achat_validity()
            except ValidationError as e:
                return {
                    'successful': False,
                    'payload': {
                        'message': str(e),
                        'removed_coupons': [coupon.id],
                    }
                }
        
        return result

    def confirm_coupon_programs(self, coupon_data):
        """
        Override to mark bon_achat coupons as fully used after order confirmation,
        regardless of the amount actually applied.
        """
        # Snapshot coupon metadata (applied/original amounts) before the parent mutates the payload
        coupon_data_snapshot = {
            int(k): deepcopy(v) if isinstance(v, dict) else v for k, v in coupon_data.items()
        }

        # Call parent method first
        result = super().confirm_coupon_programs(coupon_data)
        
        # Handle bon_achat specific logic
        # coupon_data keys are stringified when using RPC
        coupon_data_int = coupon_data_snapshot
        
        # Get all coupons that were used in this order
        used_coupon_ids = [cid for cid in coupon_data_int.keys() if cid > 0]
        bon_achat_coupons = self.env['loyalty.card'].browse(used_coupon_ids).filtered(
            lambda c: c.program_type == 'bon_achat'
        )
        
        # Mark each bon_achat as fully used
        for coupon in bon_achat_coupons:
            coupon_vals = coupon_data_int.get(coupon.id, {}) or {}
            applied_amount = coupon_vals.get('applied_amount')
            original_points = coupon_vals.get('original_points')
            if original_points is None:
                points_delta = coupon_vals.get('points')
                if isinstance(points_delta, (int, float)):
                    original_points = abs(points_delta)
            coupon.mark_bon_achat_as_used(
                self,
                applied_amount=applied_amount,
                original_points=original_points,
            )

        self._finalize_bon_achat_lines(coupon_data_int)
        
        return result

    def _process_saved_order(self, draft):
        """
        Override to handle bon_achat when processing saved orders.
        """
        res = super()._process_saved_order(draft)
        
        # Ensure bon_achat coupons used in this order are marked as used
        bon_achat_lines = self.lines.filtered(
            lambda l: l.coupon_id and l.coupon_id.program_type == 'bon_achat'
        )
        
        for line in bon_achat_lines:
            if line.coupon_id.state != 'used':
                applied_amount = abs(line.price_subtotal_incl)
                line.coupon_id.mark_bon_achat_as_used(
                    self,
                    applied_amount=applied_amount,
                    original_points=line.points_cost,
                )

        self._finalize_bon_achat_lines()
        
        return res

    # -------------------------------------------------------------------------
    # Bon d'achat helpers
    # -------------------------------------------------------------------------

    def _finalize_bon_achat_lines(self, coupon_data=None):
        """Ensure bon d'achat reward lines stay informational on the backend."""
        for order in self:
            info_lines = order.lines.filtered(
                lambda line: line.reward_id and line.reward_id.program_id.program_type == 'bon_achat'
            )
            if not info_lines:
                if order.bon_achat_applied_total:
                    order.bon_achat_applied_total = 0.0
                continue

            applied_total = 0.0
            for line in info_lines:
                payload = order._get_bon_achat_payload_for_line(line, coupon_data)
                applied_amount = payload.get('applied_amount', line.bon_achat_applied_amount) or 0.0
                original_amount = payload.get('original_points', line.bon_achat_original_amount) or applied_amount
                line_vals = {
                    'is_bon_achat_info_line': True,
                    'price_unit': 0.0,
                    'price_subtotal': 0.0,
                    'price_subtotal_incl': 0.0,
                    'bon_achat_applied_amount': applied_amount,
                    'bon_achat_original_amount': original_amount,
                }
                if not line.customer_note:
                    line_vals['customer_note'] = _("Bon d'achat")
                line.write(line_vals)
                applied_total += applied_amount

            order._apply_bon_achat_totals(applied_total)

    def _get_bon_achat_payload_for_line(self, line, coupon_data):
        if not coupon_data or not line.coupon_id:
            return {}
        key = int(line.coupon_id.id)
        return coupon_data.get(key, {}) or {}

    def _apply_bon_achat_totals(self, applied_total):
        currency = self.currency_id
        total_incl = sum(self.lines.mapped('price_subtotal_incl'))
        total_excl = sum(self.lines.mapped('price_subtotal'))
        self.write({
            'bon_achat_applied_total': applied_total,
            'amount_total': currency.round(total_incl),
            'amount_tax': currency.round(total_incl - total_excl),
        })

    def _bon_achat_requires_override(self):
        self.ensure_one()
        return bool(self.lines.filtered('is_bon_achat_info_line'))

    def _bon_achat_effective_paid_amount(self):
        self.ensure_one()
        voucher_payments = sum(
            payment.amount for payment in self.payment_ids if payment.payment_method_id.is_bon_achat_method
        )
        voucher_coverage = max((self.bon_achat_applied_total or 0.0) - voucher_payments, 0.0)
        return self.amount_paid + voucher_coverage

    def _action_pos_order_paid_with_voucher(self):
        self.ensure_one()
        effective_paid = self._bon_achat_effective_paid_amount()
        if not self.config_id.cash_rounding \
           or (self.config_id.only_round_cash_method and not any(p.payment_method_id.is_cash_count for p in self.payment_ids)):
            total = self.amount_total
        else:
            total = float_round(
                self.amount_total,
                precision_rounding=self.config_id.rounding_method.rounding,
                rounding_method=self.config_id.rounding_method.rounding_method,
            )

        difference = total - effective_paid
        if not float_is_zero(difference, precision_rounding=self.currency_id.rounding):
            if not self.config_id.cash_rounding:
                raise UserError(_("Order %s is not fully paid.", self.name))

            currency = self.currency_id
            if self.config_id.rounding_method.rounding_method == "HALF-UP":
                max_diff = currency.round(self.config_id.rounding_method.rounding / 2)
            else:
                max_diff = currency.round(self.config_id.rounding_method.rounding)

            adjusted_diff = currency.round(self.amount_total - effective_paid)
            if not abs(adjusted_diff) <= max_diff:
                raise UserError(_("Order %s is not fully paid.", self.name))

        self.write({'state': 'paid'})
        return True

    def action_pos_order_paid(self):
        bon_orders = self.filtered(lambda o: o._bon_achat_requires_override())
        regular_orders = self - bon_orders
        if regular_orders:
            super(PosOrder, regular_orders).action_pos_order_paid()
        for order in bon_orders:
            order._action_pos_order_paid_with_voucher()
        return True
