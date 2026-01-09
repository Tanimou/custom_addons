import hmac
import hashlib
import logging
import pprint

from odoo import http
from odoo.http import request

from odoo.addons.custom_payment_jeko import const

_logger = logging.getLogger(__name__)


class JekoController(http.Controller):

    @http.route(const.JEKO_SUCCESS_URL, type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def jeko_success(self, **data):
        """ Handle the redirect from Jeko after successful payment.
        
        :param dict data: The GET parameters, including 'reference'
        """
        _logger.info("Jeko success callback received with data:\n%s", pprint.pformat(data))
        
        reference = data.get('reference')
        if not reference:
            _logger.warning("Jeko success callback missing reference")
            return request.redirect('/payment/status')
        
        # Find the transaction
        tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        if not tx_sudo:
            _logger.warning("Jeko success callback: transaction not found for reference %s", reference)
            return request.redirect('/payment/status')
        
        # Check the payment status from Jeko API
        tx_sudo._jeko_check_payment_status()
        
        return request.redirect('/payment/status')

    @http.route(const.JEKO_ERROR_URL, type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def jeko_error(self, **data):
        """ Handle the redirect from Jeko after payment error.
        
        :param dict data: The GET parameters, including 'reference'
        """
        _logger.info("Jeko error callback received with data:\n%s", pprint.pformat(data))
        
        reference = data.get('reference')
        if not reference:
            _logger.warning("Jeko error callback missing reference")
            return request.redirect('/payment/status')
        
        # Find the transaction
        tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        if not tx_sudo:
            _logger.warning("Jeko error callback: transaction not found for reference %s", reference)
            return request.redirect('/payment/status')
        
        # Check the payment status from Jeko API to get error details
        tx_sudo._jeko_check_payment_status()
        
        return request.redirect('/payment/status')
    

    @http.route(const.JEKO_WEBHOOK_URL, type='json', auth='public', csrf=False, methods=['POST'])
    def jeko_webhook(self, **post):
        """
        Handle webhook notifications from Jeko.
        This endpoint receives both e-commerce AND POS Soundbox webhooks.
        """
        payload = request.jsonrequest
        _logger.info("=== JEKO WEBHOOK RECEIVED ===")
        _logger.info("Payload:\n%s", pprint.pformat(payload))
        
        # Get signature
        signature = request.httprequest.headers.get('Jeko-Signature')
        _logger.info("Jeko-Signature header: %s", signature)
        
        if not signature:
            _logger.warning("Jeko webhook missing signature header")
            return {'status': 'fail', 'message': 'Missing signature'}
        
        # Find Jeko provider for signature verification
        provider = request.env['payment.provider'].sudo().search([
            ('code', '=', 'jeko'),
            ('state', 'in', ['enabled', 'test'])
        ], limit=1)
        
        if not provider:
            _logger.error("Jeko webhook: no active Jeko provider found")
            return {'status': 'fail', 'message': 'Provider not found'}
        
        # Verify signature if webhook secret is configured
        webhook_secret = provider.jeko_webhook_secret
        if webhook_secret:
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                request.httprequest.data,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                _logger.error("Jeko webhook: INVALID SIGNATURE!")
                return {'status': 'error', 'message': 'Invalid signature'}
            
            _logger.info("Webhook signature verified successfully")
        else:
            _logger.warning("Webhook secret not configured - processing without verification")
        
        # Determine if this is e-commerce or POS webhook
        transaction_details = payload.get("transactionDetails", {})
        reference = transaction_details.get("reference")
        
        if not reference:
            _logger.error("Jeko webhook: missing reference in transactionDetails")
            return {'status': 'fail', 'message': 'Missing reference'}
        
        # Check if it's a POS payment (reference starts with "POS-")
        if reference.startswith('POS-'):
            return self._handle_pos_soundbox_webhook(payload, reference)
        else:
            return self._handle_ecommerce_webhook(payload, reference)

    def _handle_ecommerce_webhook(self, payload, reference):
        """Handle webhook for e-commerce (redirect) payments."""
        _logger.info("Processing e-commerce webhook for reference: %s", reference)
        
        # Find the transaction
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'jeko')
        ], limit=1)
        
        if not tx_sudo:
            _logger.warning("E-commerce webhook: transaction not found for reference %s", reference)
            return {'status': 'fail', 'message': 'Transaction not found'}
        
        # Process the webhook
        tx_sudo._jeko_process_payment_status(payload)
        
        _logger.info("E-commerce webhook processed successfully for transaction %s", reference)
        return {"status": "ok"}

    def _handle_pos_soundbox_webhook(self, payload, reference):
        """Handle webhook for POS Soundbox payments."""
        _logger.info("Processing POS Soundbox webhook for reference: %s", reference)
        
        # Extract device ID from webhook
        # The reference format is: POS-{order_ref}-{uuid}
        # We need to find the payment method by device ID from the payload or store
        
        # Option 1: Find by reference pattern matching
        # For now, we'll broadcast to all POS payment methods and let them filter
        
        jeko_payment_methods = request.env['pos.payment.method'].sudo().search([
            ('use_payment_terminal', '=', 'jeko_soundbox')
        ])
        
        if not jeko_payment_methods:
            _logger.warning("No Jeko Soundbox payment methods found")
            return {'status': 'fail', 'message': 'No payment methods found'}
        
        # Process webhook for each method (they will filter by their session)
        for payment_method in jeko_payment_methods:
            try:
                payment_method._jeko_process_webhook_notification(payload)
            except Exception as e:
                _logger.error("Error processing webhook for method %s: %s", payment_method.id, str(e))
        
        _logger.info("POS Soundbox webhook processed successfully")
        return {"status": "ok"}