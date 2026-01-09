/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        
        // Listen for Jeko Soundbox webhook notifications
        this.data.connectWebSocket("JEKO_SOUNDBOX_RESPONSE", () => {
            const pendingLine = this.getPendingPaymentLine("jeko_soundbox");
            
            if (pendingLine) {
                pendingLine.payment_method_id.payment_terminal.handleJekoSoundboxStatusResponse();
            }
        });
    },
});