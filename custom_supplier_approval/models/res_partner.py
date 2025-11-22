# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ResPartner(models.Model):
    """Extend res.partner with supplier approval and evaluation fields"""
    _inherit = 'res.partner'

    # Supplier Approval Fields
    supplier_approval_request_ids = fields.One2many(
        'supplier.approval.request',
        'partner_id',
        string='Approval Requests',
        help="History of approval requests for this supplier"
    )
    supplier_approved = fields.Boolean(
        string='Approved Supplier',
        compute='_compute_supplier_approved',
        store=True,
        search='_search_supplier_approved',
        help="True if this supplier has at least one approved request"
    )
    supplier_approval_date = fields.Date(
        string='Approval Date',
        compute='_compute_supplier_approval_date',
        store=True,
        help="Date when the supplier was last approved"
    )
    supplier_approval_request_count = fields.Integer(
        string='Approval Requests Count',
        compute='_compute_supplier_approval_request_count',
        help="Number of approval requests"
    )

    # Supplier Category
    supplier_category_ids = fields.Many2many(
        'supplier.category',
        'partner_supplier_category_rel',
        'partner_id',
        'category_id',
        string='Supplier Categories',
        help="Categories for classifying this supplier (supplies, services, works, etc.)"
    )

    # Legal Documents
    legal_document_ids = fields.One2many(
        'supplier.legal.document',
        'partner_id',
        string='Legal Documents',
        help="Legal documents for this supplier (RCCM, NCC, CNPS, etc.)"
    )
    supplier_legal_document_count = fields.Integer(
        string='Documents Count',
        compute='_compute_supplier_legal_document_count',
        help="Number of legal documents"
    )
    valid_legal_documents = fields.Boolean(
        string='Has Valid Documents',
        compute='_compute_valid_legal_documents',
        help="True if supplier has at least one valid legal document"
    )

    # Supplier Evaluation
    supplier_evaluation_ids = fields.One2many(
        'supplier.evaluation',
        'partner_id',
        string='Evaluations',
        help="Performance evaluations for this supplier"
    )
    supplier_evaluation_count = fields.Integer(
        string='Evaluations Count',
        compute='_compute_supplier_evaluation_count',
        help="Number of evaluations"
    )
    supplier_satisfaction_rate = fields.Float(
        string='Satisfaction Rate (%)',
        compute='_compute_supplier_satisfaction_rate',
        store=True,
        help="Average satisfaction score from all evaluations (0-100)"
    )

    @api.depends('supplier_approval_request_ids.state')
    def _compute_supplier_approved(self):
        """Compute if supplier is approved based on approval requests"""
        for partner in self:
            approved_requests = partner.supplier_approval_request_ids.filtered(
                lambda r: r.state == 'approved'
            )
            partner.supplier_approved = bool(approved_requests)

    def _search_supplier_approved(self, operator, value):
        """Search method for supplier_approved field"""
        if operator == '=' and value:
            # Find partners with approved requests
            approved_partners = self.env['supplier.approval.request'].search([
                ('state', '=', 'approved')
            ]).mapped('partner_id')
            return [('id', 'in', approved_partners.ids)]
        elif operator == '=' and not value:
            # Find partners without approved requests
            approved_partners = self.env['supplier.approval.request'].search([
                ('state', '=', 'approved')
            ]).mapped('partner_id')
            return [('id', 'not in', approved_partners.ids)]
        else:
            return []

    @api.depends('supplier_approval_request_ids.approval_date', 'supplier_approval_request_ids.state')
    def _compute_supplier_approval_date(self):
        """Compute the most recent approval date"""
        for partner in self:
            approved_requests = partner.supplier_approval_request_ids.filtered(
                lambda r: r.state == 'approved' and r.approval_date
            )
            if approved_requests:
                partner.supplier_approval_date = max(approved_requests.mapped('approval_date'))
            else:
                partner.supplier_approval_date = False

    def _compute_supplier_approval_request_count(self):
        """Compute the number of approval requests"""
        for partner in self:
            partner.supplier_approval_request_count = len(partner.supplier_approval_request_ids)

    def _compute_supplier_legal_document_count(self):
        """Compute the number of legal documents"""
        for partner in self:
            partner.supplier_legal_document_count = len(partner.legal_document_ids)

    @api.depends('legal_document_ids.state')
    def _compute_valid_legal_documents(self):
        """Check if partner has at least one valid legal document"""
        for partner in self:
            valid_docs = partner.legal_document_ids.filtered(
                lambda d: d.state == 'valid'
            )
            partner.valid_legal_documents = bool(valid_docs)

    def _compute_supplier_evaluation_count(self):
        """Compute the number of evaluations"""
        for partner in self:
            partner.supplier_evaluation_count = len(partner.supplier_evaluation_ids)

    @api.depends('supplier_evaluation_ids.overall_score')
    def _compute_supplier_satisfaction_rate(self):
        """Calculate average satisfaction rate from all evaluations"""
        for partner in self:
            evaluations = partner.supplier_evaluation_ids.filtered(lambda e: e.overall_score)
            if evaluations:
                partner.supplier_satisfaction_rate = sum(evaluations.mapped('overall_score')) / len(evaluations)
            else:
                partner.supplier_satisfaction_rate = 0.0

    def action_view_approval_requests(self):
        """Action to view all approval requests for this supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Requests'),
            'res_model': 'supplier.approval.request',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
            }
        }

    def action_view_evaluations(self):
        """Action to view all evaluations for this supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Supplier Evaluations'),
            'res_model': 'supplier.evaluation',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
            }
        }

    def action_view_legal_documents(self):
        """Action to view all legal documents for this supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Legal Documents'),
            'res_model': 'supplier.legal.document',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
            }
        }

    def action_create_approval_request(self):
        """Action to create a new approval request for this supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Approval Request'),
            'res_model': 'supplier.approval.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            }
        }
