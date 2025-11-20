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
     * Override updatePrograms to auto-apply buy_x_get_y rewards after order changes
     */
    updatePrograms() {
        const result = super.updatePrograms();
        // After programs are updated, auto-apply buy_x_get_y rewards
        this._autoApplyBuyXGetYRewardsIfEligible();
        return result;
    },

    /**
     * Override pointsForPrograms to handle buy_x_get_y per-product logic
     * For buy_x_get_y with per_product_mode: calculate points per line instead of globally
     */
    pointsForPrograms(programs) {
        // Call super first to get the base results
        const result = super.pointsForPrograms(programs);

        // Check if we need per-product handling (after super call to avoid early errors)
        try {
            // Initialize buy_x_get_y line credits storage if needed
            if (!this.uiState.buy_x_get_y_line_credits) {
                this.uiState.buy_x_get_y_line_credits = {};
            }

            // Process buy_x_get_y programs with per_product_mode
            for (const program of programs) {
                if (!program || program.program_type !== "buy_x_get_y" || !program.rule_ids) {
                    continue;
                }

                for (const rule of program.rule_ids) {
                    // Skip if rule doesn't have per_product_mode enabled
                    if (!rule || !rule.per_product_mode || rule.reward_point_mode !== "unit") {
                        continue;
                    }

                    // Reset points for this program - we'll recalculate per-line
                    result[program.id] = [];
                    let totalPoints = 0;

                    // Clear previous line credits for this program
                    const programKey = `program_${program.id}`;
                    this.uiState.buy_x_get_y_line_credits[programKey] = {};

                    // Calculate points per individual order line
                    const orderLines = this.getOrderlines().filter((line) => !line.combo_parent_id);

                    for (const line of orderLines) {
                        // Skip reward lines
                        if (line.is_reward_line) {
                            continue;
                        }

                        // Safety check for product_id
                        if (!line.product_id || !line.product_id.id) {
                            continue;
                        }

                        // Check if line product matches rule
                        const productMatches =
                            rule.any_product || (rule.validProductIds && rule.validProductIds.has(line.product_id.id));

                        if (!productMatches) {
                            continue;
                        }

                        const lineQty = line.getQuantity();

                        // Check minimum quantity per line (not globally)
                        if (lineQty >= rule.minimum_qty) {
                            const linePoints = rule.reward_point_amount * lineQty;
                            totalPoints += linePoints;

                            // Store line-level credit info
                            const lineKey = `line_${line.uuid}`;
                            this.uiState.buy_x_get_y_line_credits[programKey][lineKey] = {
                                line_uuid: line.uuid,
                                product_id: line.product_id.id,
                                quantity: lineQty,
                                points: linePoints,
                                rule_id: rule.id,
                            };
                        }
                    }

                    if (totalPoints > 0) {
                        result[program.id] = [{ points: totalPoints }];
                    }
                }
            }
        } catch (error) {
            // If any error occurs in per-product logic, log it but don't break POS
            console.warn("Error in buy_x_get_y per-product calculation:", error);
        }

        return result;
    },

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
            points_cost: 0, // Zero points - BON ACHAT uses payment method, not point deduction
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

        couponChange.points = 0; // Zero points - BON ACHAT uses payment method flow, not point deduction
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
     * Auto-apply buy_x_get_y rewards with per_product_mode
     * This method is called after order lines change to automatically claim eligible rewards
     */
    _autoApplyBuyXGetYRewardsIfEligible() {
        try {
            // Get all buy_x_get_y programs with per_product_mode
            const buyXGetYPrograms = this.models["loyalty.program"].all().filter(
                (program) =>
                    program.program_type === "buy_x_get_y" &&
                    program.rule_ids &&
                    program.rule_ids.some((r) => r && r.per_product_mode === true)
            );

            for (const program of buyXGetYPrograms) {
                // Get the first (or only) reward for this program
                const reward = program.reward_ids && program.reward_ids[0];
                if (!reward) continue;

                // Get the line credits for this program
                const programKey = `program_${program.id}`;
                const lineCredits = this.uiState.buy_x_get_y_line_credits?.[programKey] || {};

                if (Object.keys(lineCredits).length === 0) {
                    continue;
                }

                // Check if reward lines for this program already exist
                const existingRewardLines = this.lines.filter(
                    (line) =>
                        line.is_reward_line &&
                        line.reward_id?.id === reward.id &&
                        !line.coupon_id // No coupon for buy_x_get_y
                );

                if (existingRewardLines.length === 0) {
                    // No reward lines yet, auto-apply them
                    const rewardLinesData = this._getRewardLineValuesProduct({
                        reward: reward,
                        coupon_id: null,
                        quantity: Infinity,
                    });

                    if (rewardLinesData && rewardLinesData.length > 0) {
                        for (const lineData of rewardLinesData) {
                            this.applyRewardLine(lineData);
                        }
                    }
                }
            }
        } catch (error) {
            console.warn("Error in _autoApplyBuyXGetYRewardsIfEligible:", error);
        }
    },

    /**
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

    /**
     * Override _computeUnclaimedFreeProductQty to handle buy_x_get_y per-product logic
     * For buy_x_get_y with per_product_mode: calculate free qty for the specific purchased product
     */
    _computeUnclaimedFreeProductQty(reward, coupon_id, product, remainingPoints) {
        // Guard clause: only handle buy_x_get_y with per_product_mode
        if (
            !reward ||
            !reward.program_id ||
            reward.program_id.program_type !== "buy_x_get_y" ||
            !reward.program_id.rule_ids ||
            !reward.program_id.rule_ids.some((r) => r && r.per_product_mode === true)
        ) {
            return super._computeUnclaimedFreeProductQty(reward, coupon_id, product, remainingPoints);
        }

        // Per-product mode: calculate free qty based on line-specific credits for THIS product
        const programKey = `program_${reward.program_id.id}`;
        const lineCredits = this.uiState.buy_x_get_y_line_credits?.[programKey] || {};

        let totalFreeQty = 0;
        let claimedQty = 0;

        // Count already claimed reward lines for this product
        for (const line of this.getOrderlines()) {
            if (
                line.is_reward_line &&
                line._reward_product_id?.id === product.id &&
                line.reward_id?.id === reward.id
            ) {
                claimedQty += Math.abs(line.getQuantity());
            }
        }

        // Calculate free qty from lines that purchased THIS product
        for (const creditInfo of Object.values(lineCredits)) {
            // Only count credits from lines that purchased THIS product
            if (creditInfo.product_id === product.id) {
                const linePoints = creditInfo.points;
                const lineFreeQty = Math.floor(
                    (linePoints / reward.required_points) * reward.reward_product_qty
                );
                totalFreeQty += lineFreeQty;
            }
        }

        return Math.max(0, totalFreeQty - claimedQty);
    },

    /**
     * Override _getRewardLineValuesProduct to handle buy_x_get_y per-product logic
     * For buy_x_get_y with per_product_mode: each product rewards itself
     */
    _getRewardLineValuesProduct(args) {
        const reward = args["reward"];

        // Guard clause: only handle buy_x_get_y with per_product_mode
        if (
            !reward ||
            !reward.program_id ||
            reward.program_id.program_type !== "buy_x_get_y" ||
            !reward.program_id.rule_ids ||
            !reward.program_id.rule_ids.some((r) => r && r.per_product_mode === true)
        ) {
            return super._getRewardLineValuesProduct(args);
        }

        // Per-product mode: return reward lines for each qualifying product
        const programKey = `program_${reward.program_id.id}`;
        const lineCredits = this.uiState.buy_x_get_y_line_credits?.[programKey] || {};
        const rewardLines = [];

        // Group credits by product_id
        const creditsByProduct = {};
        for (const creditInfo of Object.values(lineCredits)) {
            if (!creditsByProduct[creditInfo.product_id]) {
                creditsByProduct[creditInfo.product_id] = {
                    product_id: creditInfo.product_id,
                    total_points: 0,
                    total_qty: 0,
                };
            }
            creditsByProduct[creditInfo.product_id].total_points += creditInfo.points;
            creditsByProduct[creditInfo.product_id].total_qty += creditInfo.quantity;
        }

        // For each product that has credits, create reward line using that same product
        for (const prodData of Object.values(creditsByProduct)) {
            const product = this.models["product.product"].get(prodData.product_id);
            if (!product) continue;

            // For per-product mode, we reward exactly reward_product_qty of that product
            // No need to check unclaimedQty - just give the fixed reward amount if conditions met
            const rewardQty = reward.reward_product_qty;
            const cost = reward.required_points;

            rewardLines.push({
                product_id: product.id, // Use the actual reward product, not discount product
                price_unit: -product.getPrice(
                    this.pricelist_id,
                    rewardQty,
                    product.price,
                    this.uiState.customPriceLists
                ),
                qty: rewardQty, // Reward quantity is fixed, not based on purchased quantity
                is_reward_line: true,
                _reward_product_id: product,
                points_cost: cost,
                reward_id: reward,
                coupon_id: args["coupon_id"],
                tax_ids: product.taxes_id || [],
            });
        }

        return rewardLines;
    },

});
