# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    state = fields.Selection(
        selection=[
            ('active', "Active"),
            ('used', "Used"),
            ('expired', "Expired"),
        ],
        string="State",
        default='active',
        compute='_compute_state',
        store=True,
        help="State of the card:\n"
             "- Active: Card can be used\n"
             "- Used: Card has been used (for bon_achat)\n"
             "- Expired: Card has expired"
    )
    
    source_pos_order_id = fields.Many2one(
        comodel_name='pos.order',
        string="Source POS Order",
        help="POS order where this card/voucher was used (for bon_achat)"
    )

    used_date = fields.Datetime(
        string="Used Date",
        help="Date when the bon_achat was used"
    )

    @api.depends('program_type', 'expiration_date', 'use_count', 'source_pos_order_id')
    def _compute_state(self):
        """Compute state based on usage and expiration"""
        for card in self:
            # Check expiration first
            if card.expiration_date and fields.Date.today() > card.expiration_date:
                card.state = 'expired'
            # For bon_achat: mark as used once it has been applied to a POS order
            elif card.program_type == 'bon_achat' and card.source_pos_order_id:
                card.state = 'used'
            else:
                card.state = 'active'

    def _check_bon_achat_validity(self):
        """
        Check if a bon_achat card can be used.
        Raises ValidationError if the card cannot be used.
        """
        self.ensure_one()
        
        if self.program_type != 'bon_achat':
            return True
            
        # Check if already used
        if self.state == 'used':
            raise ValidationError(_("Ce bon d'achat a déjà été utilisé."))
        
        # Check if expired
        if self.state == 'expired':
            raise ValidationError(_("Ce bon d'achat a expiré."))
        
        # Check if the program is active
        if not self.program_id.active:
            raise ValidationError(_("Le programme de ce bon d'achat n'est plus actif."))
        
        return True

    def mark_bon_achat_as_used(self, pos_order, applied_amount=None, original_points=None):
        """
        Mark a bon_achat card as fully used after POS order validation.
        
        :param pos_order: The POS order where the bon_achat was used
        :param applied_amount: The actual amount deducted on the order
        :param original_points: The original voucher value consumed
        """
        self.ensure_one()
        
        if self.program_type != 'bon_achat':
            return
        
        # Preserve the amount before zeroing the points so history reflects the consumed value
        points_before_use = self.points
        original_amount = abs(original_points) if original_points is not None else points_before_use
        applied_amount = abs(applied_amount) if applied_amount is not None else original_amount
        forfeited_amount = max((original_amount or 0) - (applied_amount or 0), 0)

        # Mark as used
        self.write({
            'source_pos_order_id': pos_order.id,
            'used_date': fields.Datetime.now(),
            'points': 0,  # Zero out remaining points
        })

        description = _( "Bon d'achat utilisé - %s", pos_order.name)
        if forfeited_amount:
            description = _(
                "Bon d'achat utilisé - %s (appliqué: %s, perdu: %s)",
                pos_order.name,
                applied_amount,
                forfeited_amount,
            )
        
        # Create history entry
        self.env['loyalty.history'].create({
            'card_id': self.id,
            'order_model': 'pos.order',
            'order_id': pos_order.id,
            'description': description,
            'used': original_amount,  # Keep loyalty ledger consistent with consumed points
            'bon_achat_applied_amount': applied_amount,
            'bon_achat_original_amount': original_amount,
        })

    def _get_applicable_programs_for_pos(self):
        """
        Override to ensure bon_achat programs are available in POS.
        This is called during POS data loading.
        """
        # This method may not exist in base, but we're adding it for clarity
        # The actual filtering happens in pos_config and pos data loading
        pass
