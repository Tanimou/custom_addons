/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

// Ensure bon_achat programs and cards are loaded into POS
patch(PosStore.prototype, {
    /**
     * Override kept to guarantee the loyalty loader runs for Bon d'achat setups.
     */
    async _loadLoyaltyData() {
        await super._loadLoyaltyData();
    },
});
