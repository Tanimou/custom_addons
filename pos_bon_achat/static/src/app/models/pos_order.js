/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

function generateRewardIdentifier() {
    return (Math.random() + 1).toString(36).substring(3);
}

patch(PosOrder.prototype, {
    /**
     * Override _applyReward to handle bon_achat specific logic
     * For bon_achat: ensure the voucher is marked as used even if partial amount
     */
    _applyReward(reward, coupon_id, args = {}) {
        if (reward.program_id.program_type !== "bon_achat") {
            return super._applyReward(reward, coupon_id, args);
        }

        const coupon = this.models["loyalty.card"].get(coupon_id);
        if (!coupon) {
            return _t("Bon d'achat invalide");
        }

        const discountProduct = reward.discount_line_product_id;
        if (!discountProduct) {
            return _t("Aucun produit de remise n'est configuré pour ce bon d'achat.");
        }

        const regularLines = this.getOrderlines().filter((line) => !line.is_reward_line);
        if (!regularLines.length) {
            return _t("Ajoutez des articles avant d'appliquer un bon d'achat.");
        }

        const regularTotals = this.getPriceWithOptions({ lines: regularLines });
        const orderTotal = Math.max(
            0,
            (regularTotals && regularTotals.taxDetails
                ? regularTotals.taxDetails.total_amount_no_rounding
                : 0) || 0
        );
        if (orderTotal <= 0) {
            return _t("Aucun montant éligible pour appliquer ce bon d'achat.");
        }

        const bonAchatAmount = coupon.points || 0;
        if (bonAchatAmount <= 0) {
            return _t("Ce bon d'achat ne contient plus de crédit.");
        }

        const amountToApply = bonAchatAmount;
        if (amountToApply <= 0) {
            return _t("Aucun montant éligible pour appliquer ce bon d'achat.");
        }

        // Remove previously generated lines for this reward/coupon so we always reflect latest amount
        for (const line of this.lines.filter(
            (orderLine) =>
                orderLine.is_reward_line &&
                orderLine.reward_id?.id === reward.id &&
                orderLine.coupon_id?.id === coupon_id
        )) {
            line.delete();
        }

        // Create an informational line with ZERO price so totals aren't affected
        // The actual payment will be handled through the BON ACHAT payment method
        const rewardIdentifierCode = generateRewardIdentifier();
        this.applyRewardLine({
            product_id: discountProduct,
            price_unit: 0, // Zero price - informational only
            qty: 1,
            reward_id: reward,
            is_reward_line: true,
            coupon_id,
            points_cost: bonAchatAmount,
            reward_identifier_code: rewardIdentifierCode,
            tax_ids: discountProduct.taxes_id,
            customer_note: coupon.code
                ? _t("Bon d'achat %s - %s", coupon.code, formatCurrency(amountToApply, this.currency.id))
                : _t("Bon d'achat - %s", formatCurrency(amountToApply, this.currency.id)),
            bon_achat_applied_amount: amountToApply,
            bon_achat_original_amount: bonAchatAmount,
            is_bon_achat_info_line: true, // Flag as informational
        });

        const couponChange =
            this.uiState.couponPointChanges[coupon_id] ||
            (this.uiState.couponPointChanges[coupon_id] = {
                coupon_id,
                program_id: reward.program_id.id,
                points: 0,
            });

        couponChange.points = -bonAchatAmount;
        couponChange.manual = true;
        couponChange.bon_achat_applied_amount = amountToApply;
        couponChange.bon_achat_original_amount = bonAchatAmount;
        couponChange.code = coupon.code || couponChange.code;

        return true;
    },

    /**
     * Check if a program is applicable
     * Override to ensure bon_achat programs are always checked for POS
     */
    _programIsApplicable(program) {
        // Bon_achat programs are always applicable in POS (they're POS-only)
        if (program.program_type === "bon_achat") {
            return true;
        }

        return super._programIsApplicable(program);
    },

    /**
     * Get export data for loyalty when validating order
     * Ensure bon_achat coupons are properly marked as used
     */
    _get_loyalty_data() {
        const loyaltyData = super._get_loyalty_data();

        // Add bon_achat specific data to ensure backend marks them as used
        if (loyaltyData && loyaltyData.couponChanges) {
            for (const [couponId, changes] of Object.entries(loyaltyData.couponChanges)) {
                const coupon = this.models["loyalty.card"].get(parseInt(couponId));
                if (coupon && coupon.program_id.program_type === "bon_achat") {
                    const extraData = this.uiState.couponPointChanges[coupon.id] || {};
                    changes.is_bon_achat = true;
                    changes.original_points = extraData.bon_achat_original_amount || coupon.points;
                    changes.applied_amount = extraData.bon_achat_applied_amount || 0;
                }
            }
        }

        return loyaltyData;
    },
});
