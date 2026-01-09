/** @odoo-module **/

import { PresetInfoPopup } from "@pos_self_order/app/components/preset_info_popup/preset_info_popup";
import { patch } from "@web/core/utils/patch";

patch(PresetInfoPopup.prototype, {
    setup() {
        super.setup();
        
        // Définir les valeurs par défaut pour la Côte d'Ivoire
        this.state.countryId = 44; // ID de base.ci (Côte d'Ivoire)
        this.state.zip = "225";
        
        // Si la Côte d'Ivoire a des états, sélectionner le premier
        const country = this.selfOrder.models["res.country"].get(44);
        if (country?.state_ids && country.state_ids.length > 0) {
            this.state.stateId = country.state_ids[0].id;
        }
    }
});