# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from uuid import uuid4

from odoo import _, api, fields, models


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    program_type = fields.Selection(
        selection_add=[('bon_achat', "Bon d'achat")],
        ondelete={'bon_achat': 'cascade'}
    )

    pos_only = fields.Boolean(
        string="POS Only",
        compute='_compute_pos_only',
        store=True,
        help="If checked, this program can only be used in Point of Sale, not in eCommerce."
    )

    bon_achat_amount = fields.Monetary(
        string="Montant du bon",
        currency_field='currency_id',
        help="Montant fixe appliqué par chaque bon d'achat généré pour ce programme."
    )

    @api.depends('program_type')
    def _compute_pos_only(self):
        """Mark bon_achat programs as POS-only"""
        for program in self:
            program.pos_only = program.program_type == 'bon_achat'

    @api.model
    def _program_items_name(self):
        """Add French label for bon_achat programs"""
        res = super()._program_items_name()
        res['bon_achat'] = _("Bons d'achat")
        return res

    @api.model
    def _program_type_default_values(self):
        """Define default values for bon_achat program type"""
        res = super()._program_type_default_values()
        
        # Bon d'achat is similar to coupons but:
        # - Each voucher card is single-use (enforced at card level, not program level)
        # - POS only
        # - Monetary amount based
        res['bon_achat'] = {
            'applies_on': 'current',
            'trigger': 'with_code',
            'portal_visible': False,
            'portal_point_name': self.env.company.currency_id.symbol,
            'limit_usage': False,  # No program-level limit; each card is independently single-use
            'max_usage': 0,  # Unlimited vouchers can be used from this program
            'pos_ok': True,  # Always available in POS
            'bon_achat_amount': 0.0,
            'rule_ids': [(5, 0, 0), (0, 0, {
                'reward_point_amount': 1,
                'reward_point_mode': 'order',
                'minimum_amount': 0,
                'minimum_qty': 0,
            })],
            'reward_ids': [(5, 0, 0), (0, 0, {
                'reward_type': 'discount',
                'discount_mode': 'per_point',
                'discount': 1,
                'discount_applicability': 'order',
                'required_points': 1,
                'description': _("Bon d'achat"),
            })],
            'communication_plan_ids': [(5, 0, 0), (0, 0, {
                'trigger': 'create',
                'mail_template_id': (
                    self.env.ref('loyalty.mail_template_loyalty_card', raise_if_not_found=False)
                    or self.env['mail.template']
                ).id,
            })],
        }
        return res

    @api.model
    def get_program_templates(self):
        """Add bon_achat template to available program templates"""
        res = super().get_program_templates()
        
        # Only show bon_achat in the discount & loyalty menu (not gift/ewallet)
        ctx_menu_type = self.env.context.get('menu_type')
        if ctx_menu_type != 'gift_ewallet':
            res['bon_achat'] = {
                'title': _("Bon d'achat"),
                'description': _("Bon à usage unique, utilisable uniquement au Point de Vente"),
                'icon': 'coupons',
            }
        return res

    @api.model
    def _get_template_values(self):
        """Add template creation values for bon_achat"""
        res = super()._get_template_values()
        program_type_defaults = self._program_type_default_values()
        
        res['bon_achat'] = {
            'name': _("Bon d'achat"),
            'program_type': 'bon_achat',
            **program_type_defaults['bon_achat']
        }
        return res

    def write(self, vals):
        """Ensure pos_ok=True for bon_achat programs"""
        res = super().write(vals)
        
        # Ensure bon_achat programs always have pos_ok = True
        # Note: No program-level usage limits enforced; each voucher card is single-use at the card level
        for program in self:
            if program.program_type == 'bon_achat':
                updates = {}
                if not program.pos_ok:
                    updates['pos_ok'] = True  # BON ACHAT programs are always available in POS
                
                if updates:
                    super(LoyaltyProgram, program).write(updates)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure pos_ok=True for bon_achat programs at creation"""
        for vals in vals_list:
            if vals.get('program_type') == 'bon_achat':
                # No program-level usage limits; each voucher card is single-use at the card level
                vals['pos_ok'] = True  # BON ACHAT programs are always available in POS
        
        return super().create(vals_list)
