/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { roundPrecision } from "@web/core/utils/numbers";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";

// Polling interval as fallback to webhook
const POLLING_INTERVAL_MS = 3000;
// Timeout maximum pour attendre la confirmation du paiement (ms)
const MAX_WAIT_TIME_MS = 2 * 60 * 1000; // 2 minutes

export class PaymentJeko extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.paymentLineResolvers = {};
    }

    sendPaymentRequest(uuid) {
        super.sendPaymentRequest(uuid);
        return this._jeko_pay(uuid);
    }

    sendPaymentCancel(order, uuid) {
        super.sendPaymentCancel(order, uuid);
        return this._jeko_cancel();
    }

    pending_jeko_line() {
        return this.pos.getPendingPaymentLine("jeko_soundbox");
    }

    _call_jeko(data, action) {
        return this.env.services.orm.silent
            .call("pos.payment.method", action, [[this.payment_method_id.id], data])
            .catch(this._handleOdooConnectionFailure.bind(this));
    }

    _handleOdooConnectionFailure(data = {}) {
        const line = this.pending_jeko_line();
        if (line) {
            line.setPaymentStatus("retry");
        }
        this._show_error(
            _t("Could not connect to the Odoo server, please check your internet connection and try again.")
        );
        return Promise.reject(data);
    }

    _jeko_handle_response(response) {
        const line = this.pending_jeko_line();
        if (!line) return Promise.reject(new Error("Payment line not found"));

        line.setPaymentStatus("waitingCard");

        if (response.error) {
            this._show_error(response.error);
            return Promise.reject(response);
        }

        if (!response.payment_request_id) {
            this._show_error("Jeko response missing payment_request_id");
            return Promise.reject(response);
        }

        // Récupère l'ID de paiement renvoyé par Odoo
        line.jeko_payment_request_id = response.payment_request_id;

        return this.waitForPaymentConfirmation(line);   
    }

    async _jeko_pay() {
        super.sendPaymentRequest(...arguments);

        const order = this.pos.getOrder();
        const line = order.getSelectedPaymentline();
        if (!line) {
            this._show_error("No payment line selected");
            return Promise.reject();
        }

        line.setPaymentStatus("waitingCard");

        // Génère une référence unique côté JS
        const randomId = Math.random().toString(36).substring(2, 10);
        const reference = `POS-${order.name}-${randomId}`;

        const data = {
            amount: roundPrecision(Math.abs(line.amount * 100)),
            reference: reference,
            pos_session_id: this.pos.session.id,
        };

        const action = "jeko_soundbox_send_payment_request";

        return this._call_jeko(data, action).then((response) =>
            this._jeko_handle_response(response)
        );
    }

    async _jeko_cancel() {
        super.sendPaymentCancel(...arguments);

        const line = this.pos.getOrder().getSelectedPaymentline();
        if (!line) return Promise.resolve(false);

        const data = {
            payment_request_id: line.jeko_payment_request_id,
        };

        return this._call_jeko(data, "jeko_soundbox_send_payment_cancel").then((response) => {
            if (response.error) {
                this._show_error(response.error);
            }
            return true;
        });
    }

    async handleJekoSoundboxStatusResponse() {
        const line = this.pending_jeko_line();
        if (!line) return;

        const notification = await this.env.services.orm.silent.call(
            "pos.payment.method",
            "get_latest_jeko_soundbox_status",
            [[this.payment_method_id.id]]
        );

        if (!notification) {
            this._handleOdooConnectionFailure();
            return;
        }

        const isPaymentSuccessful = this.isPaymentSuccessful(notification, line);

        if (isPaymentSuccessful) {
            this.handleSuccessResponse(line, notification);
        } else if (notification.error) {
            this._show_error(_t("Message from Jeko: %s", notification.error));
        }

        const resolver = this.paymentLineResolvers?.[line.uuid];
        if (resolver) {
            this.paymentLineResolvers[line.uuid] = null;
            resolver(isPaymentSuccessful);
        } else {
            line.handlePaymentResponse(isPaymentSuccessful);
        }
    }

    isPaymentSuccessful(notification, line) {
        return (
            notification &&
            notification.success === true &&
            notification.status === 'success'
        );
    }

    waitForPaymentConfirmation(line) {
        return new Promise((resolve, reject) => {
            if (!line) return reject(new Error("No payment line found"));

            const paymentRequestId = line.jeko_payment_request_id;
            if (!paymentRequestId) return reject(new Error("Missing payment_request_id"));

            this.paymentLineResolvers[line.uuid] = resolve;
            const startTime = Date.now();

            const intervalId = setInterval(async () => {
                const elapsed = Date.now() - startTime;

                const isPaymentStillValid = () =>
                    this.paymentLineResolvers[line.uuid] &&
                    this.pending_jeko_line()?.jeko_payment_request_id === paymentRequestId &&
                    line.payment_status === "waitingCard" &&
                    elapsed < MAX_WAIT_TIME_MS;

                if (!isPaymentStillValid()) {
                    clearInterval(intervalId);
                    if (elapsed >= MAX_WAIT_TIME_MS) {
                        line.setPaymentStatus("error");
                        this._show_error("Timeout waiting for payment confirmation");
                        resolve(false);
                    }
                    return;
                }

                try {
                    const result = await this._call_jeko(
                        { payment_request_id: paymentRequestId },
                        "jeko_soundbox_get_payment_status"
                    );

                    if (!result) return;

                    if (result.success === true && result.status === 'success' && isPaymentStillValid()) {
                        clearInterval(intervalId);
                        this.handleSuccessResponse(line, result);
                        this.paymentLineResolvers[line.uuid] = null;
                        resolve(true);
                    } else if (result.status === 'error' && isPaymentStillValid()) {
                        clearInterval(intervalId);
                        line.setPaymentStatus("error");
                        this._show_error(result.error || "Payment failed");
                        this.paymentLineResolvers[line.uuid] = null;
                        resolve(false);
                    }
                } catch (err) {
                    clearInterval(intervalId);
                    line.setPaymentStatus("error");
                    this._show_error(err.message || "Failed to get payment status");
                    this.paymentLineResolvers[line.uuid] = null;
                    resolve(false);
                }
            }, POLLING_INTERVAL_MS);
        });
    }

    handleSuccessResponse(line, notification) {
        if (!line) return;
        line.transaction_id = notification.transactionId || null;
        line.card_type = notification.paymentMethod || null;
        line.cardholder_name = "";
        line.setPaymentStatus("done");
    }

    _show_error(msg, title) {
        if (!title) {
            title = _t("Jeko Soundbox Error");
        }
        this.env.services.dialog.add(AlertDialog, {
            title: title,
            body: msg,
        });
    }
}

register_payment_method("jeko_soundbox", PaymentJeko);
