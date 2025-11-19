/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * Override to auto-fill BON ACHAT payment amount with voucher balance.
     * This patches the native Odoo accounting method to detect BON ACHAT payments.
     */
    getDefaultAmountDueToPayIn(paymentMethod) {
        // If this is NOT a BON ACHAT payment method, use default behavior
        if (!paymentMethod || !paymentMethod.is_bon_achat_method) {
            return super.getDefaultAmountDueToPayIn(paymentMethod);
        }

        // BON ACHAT payment method - check for voucher lines
        const bonAchatLines = this.lines.filter(
            (line) => line.is_reward_line && line.is_bon_achat_info_line
        );

        if (bonAchatLines.length > 0) {
            // Sum all bon_achat line amounts
            const totalVoucherAmount = bonAchatLines.reduce(
                (sum, line) => sum + (line.bon_achat_applied_amount || 0),
                0
            );

            if (totalVoucherAmount > 0) {
                console.log('[BON ACHAT] Auto-filling with voucher amount:', totalVoucherAmount);
                return totalVoucherAmount;
            }
        }

        // Fallback: check uiState for bon_achat_vouchers
        if (this.uiState?.bon_achat_vouchers?.length > 0) {
            const totalVoucherAmount = this.uiState.bon_achat_vouchers.reduce(
                (sum, voucher) => sum + (voucher.amount || 0),
                0
            );
            
            if (totalVoucherAmount > 0) {
                console.log('[BON ACHAT] Auto-filling from uiState:', totalVoucherAmount);
                return totalVoucherAmount;
            }
        }

        // No vouchers found, fall back to default behavior
        return super.getDefaultAmountDueToPayIn(paymentMethod);
    },
});
