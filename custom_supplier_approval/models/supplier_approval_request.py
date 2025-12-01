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
        string='Fournisseur',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Demandé par',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    request_date = fields.Date(
        string='Date de la demande',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    service_types = fields.Text(
        string='Types de services',
        help="Description des services ou produits fournis par ce fournisseur"
    )
    initial_evaluation = fields.Text(
        string='Évaluation initiale',
        help="Évaluation initiale si le fournisseur a déjà été testé"
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente d\'approbation'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
    ], string='Statut', default='draft', required=True, tracking=True)
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approuvé par',
        readonly=True,
        tracking=True
    )
    approval_date = fields.Date(
        string='Date d\'approbation',
        readonly=True,
        tracking=True
    )
    rejection_reason = fields.Text(
        string='Raison du rejet',
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
                        _('Une demande d\'approbation en attente existe déjà pour le fournisseur %s!') % rec.partner_id.name
                    )

    @api.constrains('state', 'partner_id')
    def _check_legal_documents_before_approval(self):
        """Ensure supplier has valid legal documents before approval.
        
        Exception: Suppliers with fleet partner profiles of type 'garage' or 
        'remorqueur' are exempt from this requirement.
        """
        for rec in self:
            if rec.state == 'approved':
                # Check if partner has a fleet profile with garage or remorqueur type
                # This exempts them from the legal document requirement
                is_fleet_partner_exempt = False
                if 'fleet.partner.profile' in self.env:
                    fleet_profiles = self.env['fleet.partner.profile'].search([
                        ('partner_id', '=', rec.partner_id.id),
                        ('partner_type', 'in', ['garage', 'remorqueur']),
                    ], limit=1)
                    is_fleet_partner_exempt = bool(fleet_profiles)
                
                if is_fleet_partner_exempt:
                    # Skip legal document check for garage/remorqueur fleet partners
                    continue
                
                valid_docs = rec.partner_id.legal_document_ids.filtered(
                    lambda d: d.state == 'valid'
                )
                if not valid_docs:
                    raise ValidationError(
                        _('Impossible d\'approuver le fournisseur %s sans au moins un document légal valide!') % rec.partner_id.name
                    )

    def action_submit(self):
        """Submit request for approval - transition to pending state"""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Seules les demandes en brouillon peuvent être soumises!'))
            
            # Use sudo() to change state - this is a legitimate workflow transition
            # Security rules restrict write access to draft state only, but submit action
            # is allowed for request owners through button access control
            rec.sudo().write({'state': 'pending'})
            
            # Post message to chatter
            rec.message_post(
                body=_('Demande d\'approbation soumise par %s') % self.env.user.name,
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
                    summary=_('Demande d\'approbation fournisseur à examiner'),
                    note=_('Veuillez examiner la demande d\'approbation %s pour le fournisseur %s') % (rec.name, rec.partner_id.name),
                    user_id=manager.id
                )
            
            # Notify purchase managers via message
            if purchase_managers:
                rec.message_post(
                    body=_('Une nouvelle demande d\'approbation fournisseur nécessite votre attention.'),
                    message_type='notification',
                    partner_ids=purchase_managers.mapped('partner_id').ids,
                    subtype_xmlid='mail.mt_comment'
                )

    def action_approve(self):
        """Approve request - transition to approved state"""
        # Only Purchase Managers can approve
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError(_(
                'Seuls les responsables des achats peuvent approuver les demandes de fournisseurs. '
                'Veuillez contacter votre administrateur si vous avez besoin de cet accès.'
            ))
        
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Seules les demandes en attente peuvent être approuvées!'))
            
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
            
            # Notify requester
            if rec.requested_by.partner_id:
                rec.message_post(
                    body=_('Votre demande d\'approbation pour le fournisseur %s a été approuvée.') % rec.partner_id.name,
                    message_type='notification',
                    partner_ids=[rec.requested_by.partner_id.id],
                    subtype_xmlid='mail.mt_comment'
                )

    def action_reject(self):
        """Reject request - transition to rejected state with reason"""
        # Only Purchase Managers can reject
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise AccessError(_(
                'Seuls les responsables des achats peuvent rejeter les demandes de fournisseurs. '
                'Veuillez contacter votre administrateur si vous avez besoin de cet accès.'
            ))
        
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Seules les demandes en attente peuvent être rejetées!'))
            
            if not rec.rejection_reason:
                raise UserError(_('Veuillez fournir une raison de rejet avant de rejeter la demande!'))
            
            # Use sudo() for state transition
            rec.sudo().write({'state': 'rejected'})
            
            # Mark activities as done
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            
            # Post message to chatter
            rec.message_post(
                body=_('Fournisseur rejeté par %s. Raison : %s') % (self.env.user.name, rec.rejection_reason),
                message_type='notification'
            )
            
            # Notify requester
            if rec.requested_by.partner_id:
                rec.message_post(
                    body=_('Votre demande d\'approbation pour le fournisseur %s a été rejetée. Raison : %s') % (
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
                raise UserError(_('Seules les demandes rejetées peuvent être réinitialisées à l\'état brouillon!'))
            
            # Use sudo() for state transition - users can reset their own rejected requests
            rec.sudo().write({
                'state': 'draft',
                'rejection_reason': False,
                'approved_by': False,
                'approval_date': False
            })
            
            # Post message to chatter
            rec.message_post(
                body=_('Demande réinitialisée à l\'état brouillon par %s') % self.env.user.name,
                message_type='notification'
            )

    def action_view_legal_documents(self):
        """Action to view legal documents for the supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents légaux'),
            'res_model': 'supplier.legal.document',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
            }
        }
