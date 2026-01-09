# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PaymentMethod(models.Model):
    _inherit = 'payment.method'

    jeko_payment_method = fields.Selection(
        string='Provider Mobile Money Jeko',
        selection=[
            ('wave', 'Wave'),
            ('orange', 'Orange Money'),
            ('mtn', 'MTN Mobile Money'),
            ('moov', 'Moov Money'),
            ('djamo', 'Djamo'),
        ],
        default='wave',
        help="Provider de mobile money utilisé par défaut pour cette méthode de paiement Jeko. "
             "Le client pourra changer de provider sur la page de paiement Jeko.",
    )