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
        string='Demandes d\'approbation des fournisseurs',
        help="Historique des demandes d'approbation pour ce fournisseur"
    )
    supplier_approved = fields.Boolean(
        string='Fournisseur agréé',
        compute='_compute_supplier_approved',
        store=True,
        search='_search_supplier_approved',
        help="Vrai si ce fournisseur a au moins une demande approuvée"
    )
    supplier_approval_date = fields.Date(
        string='Date d\'approbation',
        compute='_compute_supplier_approval_date',
        store=True,
        help="Date à laquelle le fournisseur a été approuvé pour la dernière fois"
    )
    supplier_approval_request_count = fields.Integer(
        string='Nombre de demandes d\'approbation',
        compute='_compute_supplier_approval_request_count',
        help="Nombre de demandes d'approbation"
    )

    # Supplier Category
    supplier_category_ids = fields.Many2many(
        'supplier.category',
        'partner_supplier_category_rel',
        'partner_id',
        'category_id',
        string='Catégories de fournisseurs',
        help="Catégories pour classer ce fournisseur (fournitures, services, travaux, etc.)"
    )

    # Legal Documents
    legal_document_ids = fields.One2many(
        'supplier.legal.document',
        'partner_id',
        string='Documents Légaux',
        help="Documents légaux pour ce fournisseur (RCCM, NCC, CNPS, etc.)"
    )
    supplier_legal_document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_supplier_legal_document_count',
        help="Nombre de documents légaux"
    )
    valid_legal_documents = fields.Boolean(
        string='Documents valides',
        compute='_compute_valid_legal_documents',
        help="Vrai si le fournisseur a au moins un document légal valide"
    )

    # Supplier Evaluation
    supplier_evaluation_ids = fields.One2many(
        'supplier.evaluation',
        'partner_id',
        string='Evaluations',
        help="Evaluations de performance pour ce fournisseur"
    )
    supplier_evaluation_count = fields.Integer(
        string='Nombre d\'évaluations',
        compute='_compute_supplier_evaluation_count',
        help="Nombre d'évaluations"
    )
    supplier_satisfaction_rate = fields.Float(
        string='Taux de satisfaction (%)',
        compute='_compute_supplier_satisfaction_rate',
        store=True,
        help="Score moyen de satisfaction de toutes les évaluations (0-100)"
    )
    
    # Supplier Toggle (bridges integer supplier_rank to boolean UI)
    is_supplier = fields.Boolean(
        string='Est un fournisseur',
        compute='_compute_is_supplier',
        inverse='_inverse_is_supplier',
        help="Cochez pour marquer ce contact comme un fournisseur"
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

    @api.depends('supplier_rank')
    def _compute_is_supplier(self):
        """Compute if partner is marked as supplier based on supplier_rank"""
        for partner in self:
            partner.is_supplier = partner.supplier_rank > 0

    def _inverse_is_supplier(self):
        """Set supplier_rank when toggling is_supplier checkbox"""
        for partner in self:
            if partner.is_supplier:
                # Mark as supplier ONLY if not already (preserve PO count)
                if partner.supplier_rank == 0:
                    partner.supplier_rank = 1
            else:
                # Unmark as supplier (reset to 0)
                partner.supplier_rank = 0

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
