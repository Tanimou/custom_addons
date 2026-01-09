# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.addons.custom_payment_jeko import const
from urllib.parse import urlencode
import time

_logger = logging.getLogger(__name__)
TIMEOUT = 10


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    # ========== JEKO SOUNDBOX FIELDS ==========
    jeko_soundbox_store_id = fields.Char(
        string='Jeko Store ID',
        help="The Jeko store UUID for this payment method"
    )
    jeko_soundbox_device_id = fields.Char(
        string='Soundbox Device ID',
        help="The physical Soundbox terminal device ID"
    )
    jeko_soundbox_payment_method = fields.Selection([
        ('wave', 'Wave'),
        ('orange', 'Orange Money'),
        ('mtn', 'MTN Mobile Money'),
        ('moov', 'Moov Money'),
        ('djamo', 'Djamo'),
    ],
        string='Mobile Money Provider',
        default='orange',
    )
    jeko_soundbox_latest_response = fields.Json(
        help='Used to buffer the latest asynchronous notification from Jeko webhook'
    )

    def _is_write_forbidden(self, fields):
        """Allow modification of latest_response even if pos_session is open."""
        whitelisted_fields = {'jeko_soundbox_latest_response'}
        return super()._is_write_forbidden(fields - whitelisted_fields)

    def _get_payment_terminal_selection(self):
        """Add Jeko Soundbox to available payment terminals."""
        return super()._get_payment_terminal_selection() + [('jeko_soundbox', 'Jeko Soundbox')]

    def _load_pos_data_fields(self, config):
        """Load additional fields needed in POS."""
        return [
            *super()._load_pos_data_fields(config),
            'jeko_soundbox_store_id',
            'jeko_soundbox_device_id',
            'jeko_soundbox_payment_method',
            'jeko_soundbox_latest_response'
        ]

    # ========== JEKO API CALLS (called from JavaScript) ==========

    def jeko_soundbox_send_payment_request(self, data):
        """Send payment request to Jeko Soundbox terminal."""
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only POS users can send Jeko payment requests"))

        self.ensure_one()

        # Vérification du provider
        provider = self.env['payment.provider'].search([
            ('code', '=', 'jeko'),
            ('state', 'in', ['enabled', 'test'])
        ], limit=1)

        if not provider:
            return {'error': _('Jeko provider not configured or inactive')}

        # Vérification des champs obligatoires
        if not self.jeko_soundbox_store_id:
            return {'error': _('Jeko Store ID is required')}
        if not self.jeko_soundbox_device_id:
            return {'error': _('Soundbox Device ID is required')}
        if not self.jeko_soundbox_payment_method:
            return {'error': _('Mobile Money Provider is required')}

        # Préparer les données
        amount = int(data.get('amount', 0))
        currency = self.company_id.currency_id.name if self.company_id.currency_id else 'XOF'
        reference = (data.get('reference') or f"POS-{int(time.time() * 1000)}").replace('/', '').replace(' ', '')

        success_url = f"{provider.get_base_url()}{const.JEKO_SUCCESS_URL}?reference={reference}"
        error_url = f"{provider.get_base_url()}{const.JEKO_ERROR_URL}?reference={reference}"

        payload = {
            "storeId": self.jeko_soundbox_store_id,
            "amountCents": amount,
            "currency": currency,
            "reference": reference,
            "paymentDetails": {
                "type": "soundbox",
                "data": {
                    "deviceId": self.jeko_soundbox_device_id,
                    "paymentMethod": self.jeko_soundbox_payment_method,
                    "successUrl": success_url,
                    "errorUrl": error_url,
                }
            }
        }

        _logger.info("=== JEKO SOUNDBOX PAYMENT REQUEST ===")
        _logger.info("Amount: %s %s", amount / 100, currency)
        _logger.info("Reference: %s", reference)
        _logger.info("Store ID: %s", self.jeko_soundbox_store_id)
        _logger.info("Device ID: %s", self.jeko_soundbox_device_id)
        _logger.info("Payment Method: %s", self.jeko_soundbox_payment_method)
        _logger.info("=====================================")

        # Envoyer la requête
        try:
            response = provider._jeko_make_request('payment_requests', method='POST', payload=payload)

            payment_request_id = response.get('id')
            if not payment_request_id:
                raise ValidationError(_("Jeko API did not return payment_request_id"))

            _logger.info("✅ Jeko Soundbox payment request created: %s", payment_request_id)
            
            # ✅ Stocker pour le webhook
            self.jeko_soundbox_latest_response = {
                'payment_request_id': payment_request_id,
                'reference': reference,
                'status': 'pending',
                'pos_session_id': data.get('pos_session_id'),
            }

            return {
                'success': True,
                'payment_request_id': payment_request_id,
                'reference': response.get('reference', reference),
                'status': response.get('status', 'pending'),
                'redirectUrl': response.get('redirectUrl'),
            }

        except Exception as e:
            _logger.error("❌ Jeko payment request failed: %s", str(e))
            return {'error': str(e)}

    def jeko_soundbox_get_payment_status(self, data):
        """Poll payment status from Jeko API (fallback to webhook)."""
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only POS users can get payment status"))

        self.ensure_one()
        
        # ✅ CORRECTION : Extraire payment_request_id du dictionnaire
        if isinstance(data, dict):
            payment_request_id = data.get('payment_request_id')
        else:
            payment_request_id = data
        
        if not payment_request_id:
            _logger.error("❌ Missing payment_request_id in data: %s", data)
            return {'error': 'Missing payment_request_id'}
        
        # Vérifier que c'est bien une chaîne
        if not isinstance(payment_request_id, str):
            _logger.error("❌ payment_request_id must be a string, got: %s (%s)", 
                         payment_request_id, type(payment_request_id).__name__)
            return {'error': 'Invalid payment_request_id format'}
        
        _logger.info("🔍 Polling payment status for: %s", payment_request_id)
        
        # Get Jeko provider
        provider = self.env['payment.provider'].search([
            ('code', '=', 'jeko'),
            ('state', 'in', ['enabled', 'test'])
        ], limit=1)
        
        if not provider:
            return {'error': 'Provider not found'}
        
        try:
            # ✅ Construire l'URL correctement avec juste l'ID
            endpoint = f'payment_requests/{payment_request_id}'
            _logger.info("🌐 Calling endpoint: %s", endpoint)
            
            response = provider._jeko_make_request(endpoint, method='GET')
            
            status = response.get('status')
            _logger.info("📊 Payment status: %s", status)
            
            if status == 'success':
                transaction = response.get('transaction', {})
                
                result = {
                    'success': True,
                    'payment_request_id': payment_request_id,
                    'status': 'success',
                    'transactionId': transaction.get('id'),
                    'paymentMethod': response.get('paymentMethod'),
                    'amount': transaction.get('amount', {}).get('amount', 0),
                }
                
                # ✅ Mettre à jour latest_response
                self.jeko_soundbox_latest_response = result
                _logger.info("✅ Payment successful")
                
                return result
                
            elif status == 'pending':
                return {'status': 'pending'}
            else:
                error_response = {
                    'error': response.get('errorReason', 'Payment failed'),
                    'status': 'error'
                }
                self.jeko_soundbox_latest_response = error_response
                _logger.warning("❌ Payment failed: %s", error_response.get('error'))
                return error_response
                
        except Exception as e:
            _logger.error("❌ Failed to get payment status: %s", str(e))
            return {'error': str(e)}

    def jeko_soundbox_send_payment_cancel(self, data):
        """Cancel a pending payment request."""
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("Only POS users can cancel payments"))

        _logger.info("🚫 Jeko payment cancellation requested: %s", data.get('payment_request_id'))
        
        # Clear latest response
        self.jeko_soundbox_latest_response = {
            'status': 'cancelled',
            'payment_request_id': data.get('payment_request_id')
        }
        
        return {'success': True, 'message': 'Cancelled'}

    def get_latest_jeko_soundbox_status(self):
        """Get the latest webhook response (called from JavaScript)."""
        self.ensure_one()
        response = self.jeko_soundbox_latest_response or {}
        _logger.info("📤 Getting latest Jeko status: %s", response)
        return response

    def _jeko_process_webhook_notification(self, webhook_data):
        """
        Process webhook notification from Jeko.
        Called from controller when webhook is received.
        """
        self.ensure_one()
        
        _logger.info("🔄 Processing webhook notification for payment method %s", self.id)
        
        # Extract transaction details
        transaction_details = webhook_data.get('transactionDetails', {})
        payment_request_id = transaction_details.get('id')
        reference = transaction_details.get('reference')
        
        if not payment_request_id:
            _logger.warning("⚠️ Webhook received without payment_request_id")
            return False
        
        # ✅ Vérifier si ce webhook concerne ce payment method
        current_response = self.jeko_soundbox_latest_response or {}
        expected_payment_request_id = current_response.get('payment_request_id')
        
        if expected_payment_request_id != payment_request_id:
            _logger.info("⏭️ Webhook not for this payment method (expected %s, got %s)", 
                       expected_payment_request_id, payment_request_id)
            return False
        
        # Store the webhook data
        status = webhook_data.get('status')
        is_success = status == 'success'
        
        self.jeko_soundbox_latest_response = {
            'success': is_success,
            'payment_request_id': payment_request_id,
            'transactionId': webhook_data.get('id'),
            'reference': reference,
            'status': status,
            'paymentMethod': webhook_data.get('paymentMethod'),
            'amount': webhook_data.get('amount', {}).get('amount', 0),
        }
        
        _logger.info("✅ Stored webhook response: %s", self.jeko_soundbox_latest_response)
        
        # Notify POS sessions
        self._send_notification_to_pos()
        
        return True

    def _send_notification_to_pos(self):
        """Send notification to all active POS sessions using this payment method."""
        self.ensure_one()
        
        _logger.info("📢 Sending notification to POS for payment method %s", self.id)
        
        # Find all POS configs using this payment method
        pos_configs = self.env['pos.config'].search([
            ('payment_method_ids', 'in', self.id)
        ])
        
        _logger.info("📢 Found %s POS configs to notify", len(pos_configs))
        
        # Notify each config
        for config in pos_configs:
            try:
                _logger.info("📤 Notifying POS config %s", config.name)
                config._notify('JEKO_SOUNDBOX_RESPONSE', {
                    'payment_method_id': self.id,
                    'config_id': config.id
                })
            except Exception as e:
                _logger.error("❌ Failed to notify config %s: %s", config.id, str(e))

    @api.constrains('use_payment_terminal')
    def _check_jeko_soundbox_config(self):
        """Validate Jeko Soundbox configuration."""
        for record in self:
            if record.use_payment_terminal == 'jeko_soundbox':
                if not record.jeko_soundbox_store_id:
                    raise UserError(_('Please configure Jeko Store ID'))
                if not record.jeko_soundbox_device_id:
                    raise UserError(_('Please configure Soundbox Device ID'))
                if not record.jeko_soundbox_payment_method:
                    raise UserError(_('Please select a Mobile Money Provider'))