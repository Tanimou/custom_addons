# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Fleet Mission Expense model for SCORE Mission Cost module.

FR-014: Mission expense consolidation
- Tracks individual expenses per mission (toll, fuel, maintenance, parking, other)
- Links to mission with amount, date, and description
- Optional vendor and analytic account for reporting
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetMissionExpense(models.Model):
    """Individual expense record linked to a mission."""
    
    _name = 'fleet.mission.expense'
    _description = 'Frais de Mission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_names_search = ['name', 'mission_id.name']

    # ========== IDENTIFICATION ==========
    
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('Nouveau'),
        help="Référence unique de la dépense (ex: EXP-00001)"
    )
    
    # ========== MISSION LINK ==========
    
    mission_id = fields.Many2one(
        'fleet.mission',
        string='Mission',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
        help="Mission associée à cette dépense"
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        related='mission_id.vehicle_id',
        store=True,
        readonly=True,
        help="Véhicule de la mission (hérité)"
    )
    
    # ========== EXPENSE DETAILS ==========
    
    expense_type = fields.Selection(
        [
            ('toll', 'Péage'),
            ('fuel', 'Carburant'),
            ('maintenance', 'Entretien'),
            ('parking', 'Stationnement'),
            ('accommodation', 'Hébergement'),
            ('meal', 'Restauration'),
            ('other', 'Autre'),
        ],
        string='Type de Dépense',
        required=True,
        default='other',
        tracking=True,
        help="Catégorie de la dépense"
    )
    
    description = fields.Char(
        string='Description',
        help="Description détaillée de la dépense"
    )
    
    amount = fields.Float(
        string='Montant',
        required=True,
        tracking=True,
        digits='Product Price',
        help="Montant de la dépense"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Date de la dépense"
    )
    
    # ========== VENDOR / PARTNER ==========
    
    vendor_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        tracking=True,
        domain="[('supplier_rank', '>', 0)]",
        help="Fournisseur ou prestataire de la dépense"
    )
    
    # ========== ANALYTIC ==========
    
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Compte Analytique',
        tracking=True,
        help="Compte analytique pour le reporting (projet/centre de coût)"
    )
    
    # ========== ATTACHMENTS ==========
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_mission_expense_attachment_rel',
        'expense_id',
        'attachment_id',
        string='Justificatifs',
        help="Documents justificatifs (factures, reçus, etc.)"
    )
    
    attachment_count = fields.Integer(
        string='Nombre de Pièces',
        compute='_compute_attachment_count',
    )
    
    # ========== STATE ==========
    
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('submitted', 'Soumis'),
            ('approved', 'Approuvé'),
            ('rejected', 'Refusé'),
        ],
        string='État',
        default='draft',
        tracking=True,
        help="État de validation de la dépense"
    )
    
    # ========== COMPANY ==========
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        related='mission_id.company_id',
        store=True,
        readonly=True,
    )
    
    # ========== NOTES ==========
    
    notes = fields.Text(
        string='Notes',
        help="Remarques et informations complémentaires"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        ('check_amount_positive', 'CHECK(amount > 0)',
         'Le montant de la dépense doit être positif!'),
    ]
    
    # ========== COMPUTED METHODS ==========
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Compute the number of attachments."""
        for expense in self:
            expense.attachment_count = len(expense.attachment_ids)
    
    # ========== CONSTRAINTS ==========
    
    @api.constrains('amount')
    def _check_amount(self):
        """Ensure amount is positive."""
        for expense in self:
            if expense.amount <= 0:
                raise ValidationError(_("Le montant de la dépense doit être supérieur à zéro."))
    
    # ========== CRUD OVERRIDES ==========
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate expense reference on creation."""
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.mission.expense') or _('Nouveau')
        
        expenses = super().create(vals_list)
        
        for expense in expenses:
            expense.message_post(
                body=_("Dépense créée: %s - %s", expense.expense_type, expense.amount),
                subject=_("Création Dépense")
            )
        
        return expenses
    
    # ========== WORKFLOW ACTIONS ==========
    
    def action_submit(self):
        """Submit expense for approval."""
        for expense in self:
            if expense.state != 'draft':
                continue
            expense.write({'state': 'submitted'})
            expense.message_post(
                body=_("Dépense soumise pour validation."),
                subject=_("Soumission")
            )
    
    def action_approve(self):
        """Approve the expense."""
        for expense in self:
            if expense.state != 'submitted':
                continue
            expense.write({'state': 'approved'})
            expense.message_post(
                body=_("Dépense approuvée par %s", self.env.user.name),
                subject=_("Approbation")
            )
    
    def action_reject(self):
        """Reject the expense."""
        for expense in self:
            if expense.state not in ('draft', 'submitted'):
                continue
            expense.write({'state': 'rejected'})
            expense.message_post(
                body=_("Dépense refusée par %s", self.env.user.name),
                subject=_("Refus")
            )
    
    def action_reset_to_draft(self):
        """Reset expense to draft state."""
        for expense in self:
            expense.write({'state': 'draft'})
            expense.message_post(
                body=_("Dépense remise en brouillon."),
                subject=_("Réinitialisation")
            )
    
    # ========== VIEW ACTIONS ==========
    
    def action_view_attachments(self):
        """Open attachments view."""
        self.ensure_one()
        return {
            'name': _("Justificatifs: %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }
