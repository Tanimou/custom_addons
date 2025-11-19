# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class LoyaltyHistory(models.Model):
    _inherit = 'loyalty.history'

    bon_achat_applied_amount = fields.Float(
        string="Bon d'achat applied amount",
        help="Actual amount deducted from the order when consuming a bon d'achat voucher.",
    )
    bon_achat_original_amount = fields.Float(
        string="Bon d'achat original amount",
        help="Original amount loaded on the bon d'achat voucher at the moment of consumption.",
    )
