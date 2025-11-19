# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_payment_method(self):
        """
        Extend the POS payment method loader to include the is_bon_achat_method field.
        This ensures the field is available in the POS frontend for payment auto-fill logic.
        """
        result = super()._loader_params_pos_payment_method()
        # Add our custom field to the list of fields to load
        result['search_params']['fields'].append('is_bon_achat_method')
        return result
