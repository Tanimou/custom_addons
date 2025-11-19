# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _get_available_loyalty_programs_domain(self):
        """
        Override to include bon_achat programs in POS.
        Bon_achat programs are POS-only and should be available in POS configs.
        """
        # Get the base domain from parent
        if hasattr(super(), '_get_available_loyalty_programs_domain'):
            domain = super()._get_available_loyalty_programs_domain()
        else:
            domain = []
        
        # Bon_achat programs are always available for POS
        # No additional filtering needed here as they are POS-only by design
        return domain
