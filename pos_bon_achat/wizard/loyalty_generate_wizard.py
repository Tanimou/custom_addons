# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'

    @api.model
    def default_get(self, fields_list):
        """Prefill amount for bon_achat based on program configuration."""
        res = super().default_get(fields_list)
        program = self.env['loyalty.program'].browse(res.get('program_id'))

        if program and program.program_type == 'bon_achat':
            # Montant du bon et validité : toujours alignés sur le programme
            res['points_granted'] = program.bon_achat_amount or 0.0
            res['valid_until'] = program.date_to or False
            res['description'] = self._get_bon_achat_description(program)

        return res

    @api.model
    def _get_bon_achat_description(self, program):
        if program and program.name:
            return _("Bon d'achat - %s") % program.name
        return _("Bon d'achat")

    @api.onchange('program_id')
    def _onchange_program_id_bon_achat(self):
        for wizard in self:
            if wizard.program_type == 'bon_achat':
                wizard.points_granted = wizard.program_id.bon_achat_amount or 0.0
                wizard.valid_until = wizard.program_id.date_to or False
                wizard.description = wizard._get_bon_achat_description(wizard.program_id)

    @api.depends('program_type', 'points_granted', 'coupon_qty')
    def _compute_confirmation_message(self):
        """Override to add specific message for bon_achat"""
        super()._compute_confirmation_message()
        
        for wizard in self:
            if wizard.program_type == 'bon_achat':
                wizard.confirmation_message = _(
                    "Vous êtes sur le point de générer %(coupon_qty)i bon(s) d'achat "
                    "d'une valeur de %(value)s %(currency)s, "
                    "utilisables uniquement au Point de Vente.",
                    coupon_qty=wizard.coupon_qty,
                    value=wizard.points_granted,
                    currency=wizard.program_id.currency_id.symbol or wizard.program_id.currency_id.name
                )

    def _get_coupon_values(self, partner):
        """Override to ensure bon_achat coupons are created with proper state"""
        vals = super()._get_coupon_values(partner)
        
        # For bon_achat, ensure the state is 'active' and ready to use
        if self.program_type == 'bon_achat':
            bon_amount = self.program_id.bon_achat_amount or 0.0
            expiration = self.program_id.date_to or False
            # Force wizard values as well to keep history/logs consistent
            self.points_granted = bon_amount
            self.valid_until = expiration
            vals.update({
                'state': 'active',
                'points': bon_amount,
                'expiration_date': expiration,
            })
        
        return vals
