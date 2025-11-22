# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SupplierApprovalBulkWizard(models.TransientModel):
    """Wizard for bulk approval/rejection of supplier approval requests"""
    _name = 'supplier.approval.bulk.wizard'
    _description = 'Supplier Approval Bulk Action Wizard'

    action = fields.Selection([
        ('approve', 'Approve Selected Requests'),
        ('reject', 'Reject Selected Requests'),
    ], string="Action", required=True, default='approve')
    
    rejection_reason = fields.Text(
        string="Rejection Reason",
        help="Required when rejecting requests. Will be applied to all selected requests."
    )
    
    request_ids = fields.Many2many(
        'supplier.approval.request',
        string="Approval Requests",
        help="Selected approval requests to process"
    )
    
    request_count = fields.Integer(
        string="Number of Requests",
        compute='_compute_request_count'
    )
    
    @api.depends('request_ids')
    def _compute_request_count(self):
        for wizard in self:
            wizard.request_count = len(wizard.request_ids)
    
    def action_confirm(self):
        """Execute the bulk action"""
        self.ensure_one()
        
        if not self.request_ids:
            raise UserError(_("Please select at least one approval request."))
        
        # Check if all requests are in pending state
        non_pending = self.request_ids.filtered(lambda r: r.state != 'pending')
        if non_pending:
            raise UserError(_(
                "Only pending requests can be processed.\n"
                "The following requests are not in pending state: %s"
            ) % ', '.join(non_pending.mapped('name')))
        
        # Perform the action
        if self.action == 'approve':
            self.request_ids.action_approve()
            message = _("%d approval request(s) have been approved successfully.") % len(self.request_ids)
        else:  # reject
            if not self.rejection_reason:
                raise UserError(_("Rejection reason is required when rejecting requests."))
            
            # Set rejection reason for all requests
            self.request_ids.write({'rejection_reason': self.rejection_reason})
            self.request_ids.action_reject()
            message = _("%d approval request(s) have been rejected.") % len(self.request_ids)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
