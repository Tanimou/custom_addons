# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SupplierEvaluation(models.Model):
    """Supplier Evaluation - Phase 3 implementation"""
    _name = 'supplier.evaluation'
    _description = 'Supplier Evaluation'
    _inherit = ['mail.thread']
    _order = 'evaluation_date desc, id desc'

    name = fields.Char(
        string='Nom de l\'évaluation',
        compute='_compute_name',
        store=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        ondelete='cascade',
        index=True,
        tracking=True
    )
    evaluated_by = fields.Many2one(
        'res.users',
        string='Évalué par',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    evaluation_date = fields.Date(
        string='Date de l\'évaluation',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Commande d\'achat',
        help="Commande d'achat liée à cette évaluation"
    )
    
    # Rating fields (1-5 stars)
    quality_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Quality', required=True)
    
    delivery_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Delivery', required=True)
    
    reactivity_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Reactivity', required=True)
    
    compliance_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Compliance', required=True)
    
    commercial_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string='Commercial', required=True)
    
    overall_score = fields.Float(
        string='Score global (%)',
        compute='_compute_overall_score',
        store=True,
        help="Moyenne des notes de toutes les évaluations (0-100)"
    )
    comments = fields.Text(
        string='Commentaires',
        help="Commentaires supplémentaires sur cette évaluation"
    )

    @api.depends('partner_id', 'evaluation_date')
    def _compute_name(self):
        """Phase 3: Compute name"""
        for evaluation in self:
            if evaluation.partner_id and evaluation.evaluation_date:
                evaluation.name = f"Évaluation {evaluation.partner_id.name} - {evaluation.evaluation_date}"
            else:
                evaluation.name = _('New Evaluation')

    @api.depends('quality_rating', 'delivery_rating', 'reactivity_rating', 
                 'compliance_rating', 'commercial_rating')
    def _compute_overall_score(self):
        """Phase 3: Calculate overall score"""
        for evaluation in self:
            ratings = [
                int(evaluation.quality_rating) if evaluation.quality_rating else 0,
                int(evaluation.delivery_rating) if evaluation.delivery_rating else 0,
                int(evaluation.reactivity_rating) if evaluation.reactivity_rating else 0,
                int(evaluation.compliance_rating) if evaluation.compliance_rating else 0,
                int(evaluation.commercial_rating) if evaluation.commercial_rating else 0,
            ]
            if all(ratings):
                # Average of 5 ratings / 5 to get score as decimal (0-1) for percentage widget
                evaluation.overall_score = (sum(ratings) / len(ratings)) / 5.0
            else:
                evaluation.overall_score = 0.0

    @api.constrains('partner_id', 'purchase_order_id')
    def _check_purchase_order_partner(self):
        """Ensure purchase order belongs to evaluated supplier"""
        for rec in self:
            if rec.purchase_order_id and rec.purchase_order_id.partner_id != rec.partner_id:
                raise ValidationError(
                    _('La commande d\'achat %s n\'appartient pas au fournisseur %s!') % 
                    (rec.purchase_order_id.name, rec.partner_id.name)
                )

    def action_view_purchase_order(self):
        """Navigate to related purchase order"""
        self.ensure_one()
        if not self.purchase_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commande d\'achat'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_supplier(self):
        """Navigate to supplier"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fournisseur'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
