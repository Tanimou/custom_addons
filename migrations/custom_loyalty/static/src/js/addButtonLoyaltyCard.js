/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
console.log("🔴 addButtonLoyaltyCard.js LOADED - Module is being imported");
patch(PaymentScreen.prototype, {

    setup() {
        super.setup();
        // ✅ Local UI-only state
        this.renduState = useState({ amount: 0 });
        console.log("🔵 PaymentScreen patched - setup complete");
    },
    async onClickLoyalty() {
        const order = this.pos.getOrder();
        if (!order) {
            this.dialog.add(AlertDialog, {
                title: _t("Aucun client"),
                body: _t("Veuillez sélectionner un client d'abord."),
            });
            return;
        }

        const partner = order.getPartner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: _t("Aucun client"),
                body: _t("Veuillez sélectionner un client d'abord."),
            });
            return;
        }

        const posId = this.pos.config && this.pos.config.id ? this.pos.config.id : false;
        const posName = this.pos.config && this.pos.config.name ? this.pos.config.name : "";
        const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
        const posNameTime = `Caisse ${posName} - ${timestamp}`;

        try {
            await this.env.services.action.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: "update.loyalty.card.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_partner_id: partner.id,
                        default_pos_id: posId,
                        default_points: 0.0,
                        default_pos_name: posNameTime,
                    },
                },
                {
                    onClose: async () => {
                        const amount = await this._fetchRenduMonnaie(partner.id);
                        this.renduState.amount = amount || 0;
                        this.render();
                        console.log("✅ Rendu monnaie updated:", this.renduState.amount);
                    },
                }
            );
        } catch (error) {
            console.error("❌ Loyalty wizard error:", error);
        }
    },

    async _fetchRenduMonnaie(partnerId) {
        try {
            const result = await this.env.services.orm.call(
                "loyalty.history",
                "search_read",
                [
                    [
                        ["card_id.partner_id", "=", partnerId],
                        ["description", "ilike", "Rendu monnaie"],
                    ],
                    ["issued", "create_date"],
                ],
                {
                    limit: 1,
                    order: "create_date desc",
                }
            );
            console.log("✅ Fetch rendu monnaie result:", result);

            return result?.length ? result[0].issued : 0;
        } catch (error) {
            console.error("❌ Fetch rendu monnaie error:", error);
            return 0;
        }
    },

    get paymentScreenStatusProps() {
        return {
            ...super.paymentScreenStatusProps,
            renduMonnaie: this.renduState.amount,
            renduMonnaieText: this.env.utils.formatCurrency(this.renduState.amount),
        };
    }


});
patch(PaymentScreenStatus.prototype, {
    get paymentScreenProps() {
        const props = super.paymentScreenProps || {};

        // Add rendu monnaie props

        return {
            ...props,
            renduMonnaie: this.renduState.amount,
            renduMonnaieText: this.env.utils.formatCurrency(this.renduState.amount),
        };
    }
});

// Register client action to handle wizard response
registry.category("actions").add("pos_add_rendu_monnaie_payment", async function (env, action) {
    const { amount, partner_name, new_balance } = action.params || {};

    console.log("🎯 Client action triggered:", action.params);
    

    

});