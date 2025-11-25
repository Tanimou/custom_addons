# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SupplierRejectionWizard(models.TransientModel):
    """Wizard to reject a supplier approval request with reason"""
    _name = 'supplier.rejection.wizard'
    _description = 'Supplier Rejection Wizard'

    approval_request_id = fields.Many2one(
        'supplier.approval.request',
        string='Demande d\'approbation',
        required=True,
        readonly=True
    )
    partner_name = fields.Char(
        string='Fournisseur',
        related='approval_request_id.partner_id.name',
        readonly=True
    )
    rejection_reason = fields.Text(
        string='Raison du rejet',
        required=True,
        help="Veuillez indiquer la raison du rejet de cette demande"
    )

    def action_confirm_rejection(self):
        """Confirm the rejection with the provided reason"""
        self.ensure_one()
        if not self.rejection_reason:
            raise UserError(_('Veuillez fournir une raison de rejet!'))
        
        # Write the rejection reason to the approval request
        self.approval_request_id.rejection_reason = self.rejection_reason
        
        # Call the reject action
        return self.approval_request_id.action_reject()
