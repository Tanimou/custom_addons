/** @odoo-module */

import { TextInputPopup } from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ControlButtons.prototype, {
    /**
     * Handle "Bon d'achat" button click
     * Opens a popup to enter the bon_achat code
     */
    async clickBonAchat() {
        this.dialog.add(TextInputPopup, {
            title: _t("Bon d'achat"),
            placeholder: _t("Saisir le code du bon d'achat"),
            getPayload: async (code) => {
                code = code.trim();
                if (code !== "") {
                    const res = await this.pos.activateBonAchat(code);
                    if (!res) {
                        return;
                    }
                    if (res === true) {
                        this.notification.add(_t("Bon d'achat appliqué."), { type: "success" });
                        return;
                    }
                    if (typeof res === "string") {
                        this.notification.add(res, { type: "danger" });
                        return;
                    }
                    if (res.message) {
                        const notifType = res.type || (res.success ? "success" : "danger");
                        this.notification.add(res.message, { type: notifType });
                    }
                }
            },
        });
    },

    /**
     * Check if there are bon_achat programs available
     */
    _hasBonAchatPrograms() {
        return this.pos.models["loyalty.program"].some(
            (p) => p.program_type === "bon_achat"
        );
    },
});
