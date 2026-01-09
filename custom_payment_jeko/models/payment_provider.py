# -*- coding: utf-8 -*-
import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from odoo.addons.custom_payment_jeko import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('jeko', 'Jeko')],
        ondelete={'jeko': 'set default'}
    )

    jeko_api_key = fields.Char(
        string='Clé API Jeko',
        required_if_provider='jeko',
        groups='base.group_system',
    )

    jeko_api_key_id = fields.Char(
        string='ID Clé API Jeko',
        required_if_provider='jeko',
        groups='base.group_system',
    )

    jeko_webhook_secret = fields.Char(
        string='Webhook Secret Jeko',
        help="Secret utilisé pour vérifier les signatures des webhooks (HMAC-SHA256)",
        groups='base.group_system',
    )

    jeko_store_name = fields.Char(
        string='Nom du Store',
        help="Nom du store Jeko (pour référence)",
    )

    jeko_store_id = fields.Char(
        string='Store ID',
        help="Identifiant unique du store Jeko (UUID)",
    )

    jeko_webhook_url = fields.Char(
        string='URL Webhook',
        compute='_compute_jeko_webhook_url',
        help="URL à configurer dans Jeko Cockpit",
    )

    
    def _compute_jeko_webhook_url(self):
        """Calcule l'URL du webhook Jeko."""
        for provider in self:
            if provider.code == 'jeko':
                base_url = provider.get_base_url()
                provider.jeko_webhook_url = f"{base_url}/payment/jeko/webhook"
            else:
                provider.jeko_webhook_url = False

    def _get_jeko_headers(self):
        """Retourne les headers pour les requêtes API Jeko."""
        self.ensure_one()
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': self.jeko_api_key or '',
            'X-API-KEY-ID': self.jeko_api_key_id or '',
        }

    def _jeko_make_request(self, endpoint, method='GET', payload=None):
        """Effectue une requête vers l'API Jeko."""
        self.ensure_one()
        url = const.JEKO_API_URL + endpoint
        headers = self._get_jeko_headers()

        _logger.info("Requête Jeko: %s %s", method, url)
        if payload:
            _logger.info("Payload Jeko: %s", payload)

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=payload, timeout=30)
            else:
                raise ValidationError(_("Méthode HTTP non supportée: %s") % method)

            _logger.info("Response Status: %s", response.status_code)
            _logger.info("Response Body: %s", response.text)

            if response.status_code not in [200, 201]:
                _logger.error("=== ERREUR JEKO ===")
                _logger.error("Status: %s", response.status_code)
                _logger.error("Réponse: %s", response.text)
                _logger.error("===================")

                try:
                    error_json = response.json()
                    error_msg = error_json.get('message', response.text)
                    if 'errors' in error_json:
                        error_msg = error_msg + " - Détails: " + str(error_json['errors'])
                    if 'extras' in error_json:
                        error_msg = error_msg + " - Extras: " + str(error_json['extras'])
                    raise ValidationError(_("Erreur API Jeko: %s") % error_msg)
                except ValueError:
                    raise ValidationError(_("Erreur API Jeko: %s - %s") % (response.status_code, response.text))

            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("Erreur API Jeko: %s", str(e))
            raise ValidationError(_("Erreur API Jeko: %s") % str(e))

    def action_jeko_test_connection(self):
        """Teste la connexion à l'API Jeko et affiche les stores disponibles."""
        self.ensure_one()
        if self.code != 'jeko':
            raise ValidationError(_("Ce fournisseur n'est pas Jeko."))

        if not self.jeko_api_key or not self.jeko_api_key_id:
            raise ValidationError(_("Veuillez configurer les clés API Jeko."))

        try:
            response = self._jeko_make_request('stores')
            stores = response if isinstance(response, list) else response.get('data', [])

            if not stores:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Aucun store'),
                        'message': _('Aucun store trouvé pour ce compte Jeko.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            store_list = ""
            for store in stores:
                store_name = store.get('name', 'Sans nom')
                store_id = store.get('id', '')
                store_list = store_list + "\n• " + store_name + " → ID: " + store_id

            store_valid = False
            configured_store_name = ""
            balance_info = ""

            if self.jeko_store_id:
                for store in stores:
                    if store.get('id') == self.jeko_store_id.strip():
                        store_valid = True
                        configured_store_name = store.get('name', '')
                        break

                if store_valid:
                    try:
                        endpoint = 'stores/' + self.jeko_store_id.strip() + '/balance'
                        balance_response = self._jeko_make_request(endpoint)
                        # CORRECTION: le champ s'appelle 'amount' pas 'balance'
                        amount_cents = balance_response.get('amount', 0)
                        currency = balance_response.get('currency', 'XOF')
                        # Convertir de centimes en unité principale
                        balance = amount_cents / 100
                        balance_info = "\n💰 Solde: " + str("{:,.2f}".format(balance)) + " " + currency
                    except Exception as e:
                        _logger.warning("Could not fetch balance: %s", str(e))
                        pass

            message = "📊 Stores disponibles:" + store_list + "\n\n"

            if self.jeko_store_id:
                if store_valid:
                    message = message + "✅ Store configuré: " + configured_store_name + balance_info
                    notif_type = 'success'
                    title = _('Connexion réussie')
                else:
                    message = message + "❌ Store ID configuré invalide!"
                    notif_type = 'warning'
                    title = _('Store invalide')
            else:
                message = message + "⚠️ Aucun Store ID configuré."
                notif_type = 'warning'
                title = _('Configuration incomplète')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': message,
                    'type': notif_type,
                    'sticky': True,
                }
            }

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Échec de connexion à Jeko: %s") % str(e))

    def action_jeko_get_balance(self):
        """Récupère le solde du store configuré."""
        self.ensure_one()
        if self.code != 'jeko':
            raise ValidationError(_("Ce fournisseur n'est pas Jeko."))

        if not self.jeko_store_id:
            raise ValidationError(_("Veuillez d'abord configurer un Store ID."))

        try:
            endpoint = 'stores/' + self.jeko_store_id.strip() + '/balance'
            response = self._jeko_make_request(endpoint)

            # CORRECTION: le champ s'appelle 'amount' pas 'balance'
            amount_cents = response.get('amount', 0)
            currency = response.get('currency', 'XOF')
            # Convertir de centimes en unité principale
            balance = amount_cents / 100

            store_name = self.jeko_store_name or self.jeko_store_id
            message = str("{:,.2f}".format(balance)) + " " + currency

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('💰 Solde de %s') % store_name,
                    'message': message,
                    'type': 'info',
                    'sticky': False,
                }
            }

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Échec de récupération du solde: %s") % str(e))
        
    def _get_default_payment_method_codes(self):
        """Retourne les codes des méthodes de paiement par défaut."""
        self.ensure_one()
        if self.code == 'jeko':
            return ['jeko']
        return super()._get_default_payment_method_codes()