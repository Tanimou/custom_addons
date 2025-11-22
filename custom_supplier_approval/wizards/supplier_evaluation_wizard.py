# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SupplierEvaluationWizard(models.TransientModel):
    """Wizard for guided supplier evaluation creation"""
    _name = 'supplier.evaluation.wizard'
    _description = 'Supplier Evaluation Wizard'

    # Step 1: Select supplier and purchase order
    partner_id = fields.Many2one(
        'res.partner',
        string="Supplier",
        required=True,
        domain=[('supplier_rank', '>', 0)]
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Related Purchase Order",
        help="Optional: Link this evaluation to a specific purchase order"
    )
    
    # Step 2: Rating criteria
    quality_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string="Quality Rating", required=True, default='3',
       help="Rate the quality of products/services delivered")
    
    delivery_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string="Delivery Time Rating", required=True, default='3',
       help="Rate the timeliness of deliveries")
    
    reactivity_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string="Reactivity Rating", required=True, default='3',
       help="Rate the supplier's responsiveness to inquiries and issues")
    
    compliance_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string="Compliance Rating", required=True, default='3',
       help="Rate the supplier's administrative and regulatory compliance")
    
    commercial_terms_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'),
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐'),
    ], string="Commercial Terms Rating", required=True, default='3',
       help="Rate the commercial relationship and terms (pricing, payment, etc.)")
    
    comments = fields.Text(
        string="Comments",
        help="Additional comments about this evaluation"
    )
    
    # Preview
    overall_score_preview = fields.Float(
        string="Overall Score Preview",
        compute='_compute_overall_score_preview',
        help="Calculated automatically based on the 5 criteria ratings"
    )
    
    @api.depends('quality_rating', 'delivery_rating', 'reactivity_rating',
                 'compliance_rating', 'commercial_terms_rating')
    def _compute_overall_score_preview(self):
        for wizard in self:
            ratings = [
                int(wizard.quality_rating or 0),
                int(wizard.delivery_rating or 0),
                int(wizard.reactivity_rating or 0),
                int(wizard.compliance_rating or 0),
                int(wizard.commercial_terms_rating or 0),
            ]
            if any(ratings):
                # Calculate as decimal (0-1) for percentage widget display
                wizard.overall_score_preview = sum(ratings) / 25.0
            else:
                wizard.overall_score_preview = 0.0
    
    @api.constrains('partner_id')
    def _check_supplier_approved(self):
        """Ensure we only evaluate approved suppliers"""
        for wizard in self:
            if wizard.partner_id and not wizard.partner_id.supplier_approved:
                raise ValidationError(_(
                    "You can only evaluate approved suppliers. "
                    "Please approve '%s' first before creating an evaluation."
                ) % wizard.partner_id.name)
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Filter purchase orders by selected supplier"""
        if self.partner_id:
            return {
                'domain': {
                    'purchase_order_id': [
                        ('partner_id', '=', self.partner_id.id),
                        ('state', 'in', ['purchase', 'done'])
                    ]
                }
            }
        return {'domain': {'purchase_order_id': []}}
    
    def action_create_evaluation(self):
        """Create the supplier evaluation"""
        self.ensure_one()
        
        # Create the evaluation
        evaluation = self.env['supplier.evaluation'].create({
            'partner_id': self.partner_id.id,
            'purchase_order_id': self.purchase_order_id.id if self.purchase_order_id else False,
            'evaluation_date': fields.Date.today(),
            'evaluated_by': self.env.user.id,
            'quality_rating': self.quality_rating,
            'delivery_rating': self.delivery_rating,
            'reactivity_rating': self.reactivity_rating,
            'compliance_rating': self.compliance_rating,
            'commercial_terms_rating': self.commercial_terms_rating,
            'comments': self.comments,
        })
        
        # Return action to open the created evaluation
        return {
            'type': 'ir.actions.act_window',
            'name': _('Supplier Evaluation'),
            'res_model': 'supplier.evaluation',
            'res_id': evaluation.id,
            'view_mode': 'form',
            'target': 'current',
        }
