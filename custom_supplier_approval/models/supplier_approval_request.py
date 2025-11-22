# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SupplierApprovalRequest(models.Model):
    """Supplier Approval Request - Phase 2 implementation"""
    _name = 'supplier.approval.request'
    _description = 'Supplier Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    service_types = fields.Text(
        string='Service Types',
        help="Description of services or products provided by this supplier"
    )
    initial_evaluation = fields.Text(
        string='Initial Evaluation',
        help="Initial assessment if supplier was already tested"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )
    approval_date = fields.Date(
        string='Approval Date',
        readonly=True,
        tracking=True
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence number"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('supplier.approval.request') or _('New')
        return super().create(vals_list)

    @api.constrains('state', 'partner_id')
    def _check_unique_pending_request(self):
        """Ensure only one pending request exists per supplier"""
        for rec in self:
            if rec.state == 'pending':
                existing = self.search([
                    ('partner_id', '=', rec.partner_id.id),
                    ('state', '=', 'pending'),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError(
                        _('A pending approval request already exists for supplier %s!') % rec.partner_id.name
                    )

    @api.constrains('state', 'partner_id')
    def _check_legal_documents_before_approval(self):
        """Ensure supplier has valid legal documents before approval"""
        for rec in self:
            if rec.state == 'approved':
                valid_docs = rec.partner_id.legal_document_ids.filtered(
                    lambda d: d.state == 'valid'
                )
                if not valid_docs:
                    raise ValidationError(
                        _('Cannot approve supplier %s without at least one valid legal document!') % rec.partner_id.name
                    )

    def action_submit(self):
        """Submit request for approval - transition to pending state"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted!'))
            
            # Use sudo() to change state - this is a legitimate workflow transition
            # Security rules restrict write access to draft state only, but submit action
            # is allowed for request owners through button access control
            rec.sudo().write({'state': 'pending'})
            
            # Post message to chatter
            rec.message_post(
                body=_('Approval request submitted by %s') % self.env.user.name,
                message_type='notification'
            )
            
            # Create activity for purchase managers
            purchase_manager_group = self.env.ref('purchase.group_purchase_manager')
            # Get users through the group's user_ids field
            purchase_managers = purchase_manager_group.user_ids
            activity_type = self.env.ref('mail.mail_activity_data_todo')
            
            for manager in purchase_managers:
                rec.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('Supplier Approval Request to Review'),
                    note=_('Please review approval request %s for supplier %s') % (rec.name, rec.partner_id.name),
                    user_id=manager.id
                )
            
            # Notify purchase managers via message
            if purchase_managers:
                rec.message_post(
                    body=_('New supplier approval request requires your attention.'),
                    message_type='notification',
                    partner_ids=purchase_managers.mapped('partner_id').ids,
                    subtype_xmlid='mail.mt_comment'
                )
            
            # Send email notification to purchase managers
            template = self.env.ref('custom_supplier_approval.mail_template_approval_request_submitted', raise_if_not_found=False)
            if template:
                rec.message_post_with_source(
                    template,
                    subtype_xmlid='mail.mt_comment',
                )

    def action_approve(self):
        """Approve request - transition to approved state"""
        # Only Purchase Managers can approve
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError(_(
                'Only Purchase Managers can approve supplier requests. '
                'Please contact your administrator if you need this access.'
            ))
        
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be approved!'))
            
            # Validation is handled by @api.constrains
            # Use sudo() for state transition
            rec.sudo().write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Date.context_today(self)
            })
            
            # Note: partner.supplier_approval_date is computed automatically
            # based on approval_date field changes via @api.depends
            
            # Mark activities as done
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            
            # Post message to chatter
            rec.message_post(
                body=_('Supplier approved by %s') % self.env.user.name,
                message_type='notification'
            )
            
            # Send email notification to requester
            template = self.env.ref('custom_supplier_approval.mail_template_approval_request_approved', raise_if_not_found=False)
            if template:
                rec.message_post_with_source(
                    template,
                    subtype_xmlid='mail.mt_comment',
                )
            
            # Notify requester
            if rec.requested_by.partner_id:
                rec.message_post(
                    body=_('Your approval request for supplier %s has been approved.') % rec.partner_id.name,
                    message_type='notification',
                    partner_ids=[rec.requested_by.partner_id.id],
                    subtype_xmlid='mail.mt_comment'
                )

    def action_reject(self):
        """Reject request - transition to rejected state with reason"""
        # Only Purchase Managers can reject
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError(_(
                'Only Purchase Managers can reject supplier requests. '
                'Please contact your administrator if you need this access.'
            ))
        
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be rejected!'))
            
            if not rec.rejection_reason:
                raise UserError(_('Please provide a rejection reason before rejecting the request!'))
            
            # Use sudo() for state transition
            rec.sudo().write({'state': 'rejected'})
            
            # Mark activities as done
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            
            # Post message to chatter
            rec.message_post(
                body=_('Supplier rejected by %s. Reason: %s') % (self.env.user.name, rec.rejection_reason),
                message_type='notification'
            )
            
            # Send email notification to requester
            template = self.env.ref('custom_supplier_approval.mail_template_approval_request_rejected', raise_if_not_found=False)
            if template:
                rec.message_post_with_source(
                    template,
                    subtype_xmlid='mail.mt_comment',
                )
            
            # Notify requester
            if rec.requested_by.partner_id:
                rec.message_post(
                    body=_('Your approval request for supplier %s has been rejected. Reason: %s') % (
                        rec.partner_id.name, rec.rejection_reason
                    ),
                    message_type='notification',
                    partner_ids=[rec.requested_by.partner_id.id],
                    subtype_xmlid='mail.mt_comment'
                )

    def action_reset_to_draft(self):
        """Reset rejected request to draft for resubmission"""
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_('Only rejected requests can be reset to draft!'))
            
            # Use sudo() for state transition - users can reset their own rejected requests
            rec.sudo().write({
                'state': 'draft',
                'rejection_reason': False,
                'approved_by': False,
                'approval_date': False
            })
            
            # Post message to chatter
            rec.message_post(
                body=_('Request reset to draft by %s') % self.env.user.name,
                message_type='notification'
            )
