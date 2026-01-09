/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup() {
        super.setup(...arguments);
        this.jeko_payment_request_id = null;
    },
    
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this.jeko_payment_request_id) {
            json.jeko_payment_request_id = this.jeko_payment_request_id;
        }
        return json;
    },
});