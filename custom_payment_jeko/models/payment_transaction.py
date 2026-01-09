import logging
from urllib.parse import urlencode
from odoo import fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.custom_payment_jeko import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    jeko_payment_request_id = fields.Char(
        string="Jeko Payment Request ID",
        help="The ID of the payment request in Jeko system",
        readonly=True,
    )

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Jeko-specific rendering values. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'jeko':
            return res

        provider = self.provider_id
        base_url = provider.get_base_url()
        amount_cents = int(self.amount * 100)
        
        # URLs de retour
        success_url = f"{base_url}{const.JEKO_SUCCESS_URL}?{urlencode({'reference': self.reference})}"
        error_url = f"{base_url}{const.JEKO_ERROR_URL}?{urlencode({'reference': self.reference})}"
        
        # PAYLOAD pour paiement par redirection
        # Note: paymentMethod est requis par l'API même pour redirect
        # Récupère la méthode configurée dans payment.method (par défaut: wave)
        payment_method = self.payment_method_id
        default_method = payment_method.jeko_payment_method if payment_method else 'orange'
        reference = "%s-%s" % (
                    self.reference or "",
                    fields.Date.today().strftime("%d-%m-%Y")
                )
        
        payload = {
            "amountCents": amount_cents,
            "currency": self.currency_id.name,
            "reference": reference,
            "storeId": provider.jeko_store_id.strip() if provider.jeko_store_id else "",
            "paymentDetails": {
                "type": "redirect",
                "data": {
                    "paymentMethod": default_method,
                    "successUrl": success_url,
                    "errorUrl": error_url,
                }
            }
        }

        _logger.info("=== JEKO PAYMENT REQUEST ===")
        _logger.info("URL: %s", const.JEKO_API_URL + "payment_requests")
        _logger.info("Payload: %s", payload)
        _logger.info("============================")

        try:
            response_data = provider._jeko_make_request(
                'payment_requests',
                method='POST',
                payload=payload
            )
            _logger.info("Réponse Jeko: %s", response_data)
        except ValidationError as error:
            _logger.error("Failed to create Jeko payment request: %s", error)
            self._set_error(str(error))
            return {}

        payment_request_id = response_data.get('id')
        redirect_url = response_data.get('redirectUrl')
        
        if not redirect_url:
            error_msg = _("La réponse de Jeko ne contient pas d'URL de redirection")
            _logger.error(error_msg)
            self._set_error(error_msg)
            return {}

        self.jeko_payment_request_id = payment_request_id
        _logger.info("Created Jeko payment request %s for transaction %s", payment_request_id, self.reference)

        return {'api_url': redirect_url}

    def _jeko_check_payment_status(self):
        """ Check the payment status from Jeko API (called from success/error callbacks). """
        self.ensure_one()
        
        if not self.jeko_payment_request_id:
            _logger.warning("No Jeko payment request ID for transaction %s", self.reference)
            return

        try:
            response_data = self.provider_id._jeko_make_request(
                f'payment_requests/{self.jeko_payment_request_id}',
                method='GET'
            )
            _logger.info("Payment status check for %s: %s", self.reference, response_data)
            self._jeko_process_payment_status(response_data)
        except ValidationError as error:
            _logger.error("Failed to check Jeko payment status: %s", error)
            self._set_error(str(error))

    def _jeko_process_payment_status(self, data):
        """ Process payment status from either API response or webhook notification.
        
        This method handles two different data formats:
        1. API response format (from GET /payment_requests/{id})
        2. Webhook notification format (from POST /webhook)
        
        :param dict data: Payment data from API or webhook
        """
        self.ensure_one()
        
        # Déterminer le format des données
        is_webhook = 'transactionDetails' in data
        
        if is_webhook:
            # Format webhook
            status = data.get('status')
            transaction_id = data.get('id')
            payment_method = data.get('paymentMethod')
            transaction_details = data.get('transactionDetails', {})
            payment_request_id = transaction_details.get('id')
            
            _logger.info("Processing webhook notification for %s - Status: %s", self.reference, status)
        else:
            # Format API response
            status = data.get('status')
            payment_request_id = data.get('id')
            payment_method = data.get('paymentMethod')
            transaction = data.get('transaction', {})
            transaction_id = transaction.get('id')
            
            _logger.info("Processing API response for %s - Status: %s", self.reference, status)
        
        # Vérifier que le payment_request_id correspond
        if payment_request_id and self.jeko_payment_request_id:
            if payment_request_id != self.jeko_payment_request_id:
                _logger.warning(
                    "Payment request ID mismatch for %s: expected %s, got %s",
                    self.reference,
                    self.jeko_payment_request_id,
                    payment_request_id
                )
        
        # Traiter selon le statut
        if status == 'success':
            # Enregistrer la référence de la transaction Jeko
            if transaction_id:
                self.provider_reference = transaction_id
            
            # Enregistrer la méthode de paiement utilisée si disponible
            if payment_method and not self.payment_method_id.code:
                _logger.info("Payment completed via %s for transaction %s", payment_method, self.reference)
            
            self._set_done()
            _logger.info("Transaction %s marked as done", self.reference)
            
        elif status == 'pending':
            self._set_pending()
            _logger.info("Transaction %s is pending", self.reference)
            
        elif status in ['error', 'failed', 'cancelled']:
            # Extraire le message d'erreur
            if is_webhook:
                error_message = data.get('errorReason', _('Paiement échoué'))
            else:
                error_message = data.get('errorReason') or data.get('errorMessage', _('Paiement échoué'))
            
            self._set_error(error_message)
            _logger.warning("Transaction %s failed: %s", self.reference, error_message)
            
        else:
            _logger.warning("Unknown payment status '%s' for transaction %s", status, self.reference)

    def _process_notification_data(self, notification_data):
        """ Override to handle Jeko webhook notifications.
        
        This is called automatically by Odoo's payment flow when webhook data is received.
        
        :param dict notification_data: The webhook payload
        """
        super()._process_notification_data(notification_data)
        
        if self.provider_code != 'jeko':
            return
        
        _logger.info("Processing notification data for Jeko transaction %s", self.reference)
        self._jeko_process_payment_status(notification_data)