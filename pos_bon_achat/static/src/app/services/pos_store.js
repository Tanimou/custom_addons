/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Activate a Bon d'achat code
     * Similar to activateCode but specifically for bon_achat programs
     * 
     * @param {string} code - The bon d'achat code
     * @returns {Promise<true|string>} - true if successful, error message string otherwise
     */
    async activateBonAchat(code) {
        const order = this.getOrder();

        // Check if this code was already activated
        if (order._code_activated_coupon_ids.find((coupon) => coupon.code === code)) {
            return {
                success: false,
                message: _t("Ce bon d'achat a déjà été scanné et activé."),
                type: "warning",
            };
        }

        const customerId = order.getPartner() ? order.getPartner().id : false;

        // Call backend to validate the bon_achat code
        const { successful, payload } = await this.data.call("pos.config", "use_coupon_code", [
            [this.config.id],
            code,
            order.date_order,
            customerId,
            order.pricelist_id ? order.pricelist_id.id : false,
        ]);

        if (!successful) {
            return {
                success: false,
                message: payload.error_message,
                type: "danger",
            };
        }

        // Verify it's actually a bon_achat program
        const program = this.models["loyalty.program"].get(payload.program_id);
        if (!program || program.program_type !== "bon_achat") {
            return {
                success: false,
                message: _t("Ce code n'est pas un bon d'achat valide."),
                type: "danger",
            };
        }

        // Create the loyalty card (coupon) in the frontend
        const coupon = this.models["loyalty.card"].create({
            id: payload.coupon_id,
            code: code,
            program_id: program,
            partner_id: this.models["res.partner"].get(payload.partner_id),
            points: payload.points,
        });

        // Add to activated coupons without overwriting previously scanned codes
        if (!order._code_activated_coupon_ids) {
            order._code_activated_coupon_ids = [];
        }
        order._code_activated_coupon_ids.push(["link", coupon]);

        // Store bon d'achat amount in order UI state for payment auto-fill
        const bonAchatAmount = coupon.points || 0;
        if (!order.uiState.bon_achat_vouchers) {
            order.uiState.bon_achat_vouchers = [];
        }
        order.uiState.bon_achat_vouchers.push({
            coupon_id: coupon.id,
            code: code,
            amount: bonAchatAmount,
            program_id: program.id,
        });

        // Add informational line to show voucher has been applied
        // But do NOT apply reward calculation (totals remain unchanged)
        const discountProduct = program.discount_line_product_id;
        if (discountProduct) {
            const productModel = this.models["product.product"].get(discountProduct.id);
            if (productModel) {
                order.addOrderline({
                    product_id: productModel,
                    quantity: 1,
                    price_unit: 0, // Zero price so totals aren't affected
                    is_reward_line: true,
                    coupon_id: coupon.id,
                    points_cost: bonAchatAmount,
                    customer_note: _t("Bon d'achat %s - %s", code, formatCurrency(bonAchatAmount, order.currency.id)),
                    is_bon_achat_info_line: true, // Flag as informational only (matches backend naming)
                    bon_achat_applied_amount: bonAchatAmount, // Store the voucher amount for payment auto-fill
                    bon_achat_original_amount: bonAchatAmount,
                });
            }
        }

        return {
            success: true,
            message: _t(
                "Bon d'achat %s enregistré (%s).\nSélectionnez le mode de paiement BON ACHAT lors du règlement.",
                code,
                formatCurrency(bonAchatAmount, order.currency.id)
            ),
            type: "success",
            appliedAmount: bonAchatAmount,
        };
    },
});
