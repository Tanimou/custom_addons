/** @odoo-module **/
/**
 * Self-Order Notification Badge for POS Navbar
 * 
 * Adds a red badge on the "Orders" button showing the count of unread
 * orders from self-order interface (mobile/kiosk), and plays a sound
 * notification when new self-orders arrive.
 */

import { onMounted, useState } from "@odoo/owl";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        
        // Reactive state for self-order notifications
        this.selfOrderState = useState({
            unreadCount: 0,
            seenOrderIds: new Set(),
            lastCheckTimestamp: null,
        });
        
        // Bind the notification handler
        this._boundCheckForNewSelfOrders = this._checkForNewSelfOrders.bind(this);
        
        onMounted(() => {
            this._setupSelfOrderNotifications();
            // Initial check for existing self-orders
            this._checkForNewSelfOrders();
        });
    },
    
    /**
     * Setup WebSocket listener for ORDER_STATE_CHANGED notifications
     * This channel is triggered when self-order customers place orders
     */
    _setupSelfOrderNotifications() {
        try {
            // Connect to the ORDER_STATE_CHANGED channel
            this.pos.data.connectWebSocket("ORDER_STATE_CHANGED", this._boundCheckForNewSelfOrders);
            console.log("[SelfOrderBadge] Connected to ORDER_STATE_CHANGED channel");
        } catch (error) {
            console.warn("[SelfOrderBadge] Could not connect to websocket:", error);
        }
    },
    
    /**
     * Check for new self-orders and update the badge count
     * Self-orders are identified by source = 'mobile' or 'kiosk'
     */
    _checkForNewSelfOrders() {
        try {
            // Get all open (non-finalized) orders
            const allOrders = this.pos.models["pos.order"].filter(
                order => !order.finalized
            );
            
            // Filter for self-order sources (mobile app or kiosk)
            const selfOrders = allOrders.filter(
                order => ['mobile', 'kiosk'].includes(order.source)
            );
            
            // Find orders we haven't seen yet
            const newOrders = selfOrders.filter(
                order => !this.selfOrderState.seenOrderIds.has(order.id)
            );
            
            if (newOrders.length > 0) {
                console.log(`[SelfOrderBadge] Found ${newOrders.length} new self-orders`);
                
                // Play notification sound
                this._playSelfOrderSound();
                
                // Update unread count (total unseen self-orders)
                this.selfOrderState.unreadCount = newOrders.length;
                this.selfOrderState.lastCheckTimestamp = new Date().toISOString();
            }
        } catch (error) {
            console.warn("[SelfOrderBadge] Error checking for self-orders:", error);
        }
    },
    
    /**
     * Play the notification sound for new self-orders
     * Uses the existing 'order-receive-tone' from mail.sound_effects service
     */
    _playSelfOrderSound() {
        try {
            const soundService = this.env.services["mail.sound_effects"];
            if (soundService) {
                soundService.play("order-receive-tone");
                console.log("[SelfOrderBadge] Played order-receive-tone sound");
            } else {
                // Fallback: try using notification sound
                console.warn("[SelfOrderBadge] Sound service not available");
            }
        } catch (error) {
            console.warn("[SelfOrderBadge] Could not play sound:", error);
        }
    },
    
    /**
     * Mark all self-orders as seen when navigating to TicketScreen
     * This resets the badge counter
     */
    _markSelfOrdersAsSeen() {
        try {
            const selfOrders = this.pos.models["pos.order"].filter(
                order => ['mobile', 'kiosk'].includes(order.source)
            );
            
            // Add all current self-order IDs to the seen set
            selfOrders.forEach(order => {
                this.selfOrderState.seenOrderIds.add(order.id);
            });
            
            // Reset the counter
            this.selfOrderState.unreadCount = 0;
            console.log("[SelfOrderBadge] Marked all self-orders as seen, reset badge");
        } catch (error) {
            console.warn("[SelfOrderBadge] Error marking orders as seen:", error);
        }
    },
    
    /**
     * Getter for the self-order badge count (for template binding)
     */
    get selfOrderBadgeCount() {
        return this.selfOrderState.unreadCount;
    },
    
    /**
     * Click handler for the Orders button (replaces t-on-click in template)
     * Marks orders as seen and navigates to TicketScreen
     */
    onOrdersButtonClick() {
        // Mark orders as seen before navigating
        this._markSelfOrdersAsSeen();
        
        // Navigate to TicketScreen
        this.pos.navigate("TicketScreen");
    },
});
