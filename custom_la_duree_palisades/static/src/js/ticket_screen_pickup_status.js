/** @odoo-module **/
/**
 * TicketScreen Pickup Status Extension
 * 
 * Adds pickup status selection functionality for self-order paid orders.
 * - Adds onPickupStatusChange() handler to persist status changes
 * 
 * @module custom_la_duree_palisades.TicketScreenPickupStatus
 */

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    /**
     * Handle pickup status change from the select dropdown
     * Saves the new status to the order record via RPC
     * 
     * @param {Object} order - The order record being modified
     * @param {Event} ev - The change event from the select element
     */
    async onPickupStatusChange(order, ev) {
        const newStatus = ev.target.value;
        const oldStatus = order.pickup_status || 'waiting';
        
        if (newStatus === oldStatus) {
            return;
        }
        
        // Update local state immediately for responsiveness
        order.pickup_status = newStatus;
        
        try {
            // Persist to database
            await this.env.services.orm.write('pos.order', [order.id], {
                pickup_status: newStatus
            });
            
            // Visual feedback based on status
            if (newStatus === 'picked_up') {
                this.notification.add(
                    `Commande ${order.name} marquée comme retirée`,
                    { type: 'success', sticky: false }
                );
            }
        } catch (error) {
            // Revert on error
            order.pickup_status = oldStatus;
            ev.target.value = oldStatus;
            
            this.notification.add(
                'Erreur lors de la mise à jour du statut',
                { type: 'danger', sticky: false }
            );
            console.error('Failed to update pickup status:', error);
        }
    },
});
