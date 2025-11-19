# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_bon_achat_method = fields.Boolean(
        string="Bon d'achat payment method",
        default=False,
        help="Enable this checkbox for the payment method dedicated to Bon d'achat voucher redemptions. "
             "When a cashier selects this method, the POS will auto-fill the payment amount with the value "
             "of the applied Bon d'achat vouchers."
    )

    @api.model
    def _load_pos_data_fields(self, config):
        """
        Override to include the is_bon_achat_method field in POS data loading.
        This ensures the field is available in the POS frontend.
        """
        fields = super()._load_pos_data_fields(config)
        if 'is_bon_achat_method' not in fields:
            fields.append('is_bon_achat_method')
        _logger.debug("POS Bon Achat loader fields: %%s", fields)
        return fields
