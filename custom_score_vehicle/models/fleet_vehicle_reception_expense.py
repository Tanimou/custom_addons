# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Vehicle Reception Expense Model (FR-009)

Tracks initial expenses incurred during vehicle reception:
- Registration fees
- Insurance setup
- Documentation costs
- Transport/delivery costs
- Any other reception-related expenses

This allows SCORE to track the Total Cost of Ownership (TCO) from day one.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FleetVehicleReceptionExpense(models.Model):
    """Track reception expenses for fleet vehicles."""
    
    _name = 'fleet.vehicle.reception.expense'
    _description = 'Frais de Réception Véhicule'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # =========================================================================
    # FIELDS
    # =========================================================================
    
    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        domain="[('active', '=', True)]",
    )
    
    expense_type_id = fields.Many2one(
        'fleet.vehicle.reception.expense.type',
        string='Type de Frais',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    
    amount = fields.Monetary(
        string='Montant',
        required=True,
        tracking=True,
        currency_field='currency_id',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    
    description = fields.Text(
        string='Description',
        help="Description détaillée de la dépense.",
    )
    
    vendor_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        domain="[('supplier_rank', '>', 0)]",
        tracking=True,
        help="Fournisseur ou prestataire de service.",
    )
    
    invoice_reference = fields.Char(
        string='Référence Facture',
        help="Numéro de facture ou référence du fournisseur.",
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_reception_expense_attachment_rel',
        'expense_id',
        'attachment_id',
        string='Pièces Jointes',
        help="Factures, reçus ou autres documents justificatifs.",
    )
    
    attachment_count = fields.Integer(
        string='Nb Pièces Jointes',
        compute='_compute_attachment_count',
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        related='vehicle_id.company_id',
        store=True,
        readonly=True,
    )
    
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('confirmed', 'Confirmé'),
            ('cancelled', 'Annulé'),
        ],
        string='État',
        default='draft',
        required=True,
        tracking=True,
    )
    
    # Analytic fields (for accounting integration)
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Compte Analytique',
        help="Compte analytique pour l'imputation comptable.",
    )
    
    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('vehicle_id', 'expense_type_id', 'date')
    def _compute_name(self):
        """Compute expense reference name."""
        for expense in self:
            parts = []
            if expense.expense_type_id:
                parts.append(expense.expense_type_id.name)
            if expense.vehicle_id:
                parts.append(expense.vehicle_id.license_plate or expense.vehicle_id.name)
            if expense.date:
                parts.append(expense.date.strftime('%d/%m/%Y'))
            
            expense.name = ' - '.join(parts) if parts else _('Nouveau Frais')
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Compute attachment count."""
        for expense in self:
            expense.attachment_count = len(expense.attachment_ids)
    
    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    
    @api.constrains('amount')
    def _check_amount_positive(self):
        """Ensure amount is positive."""
        for expense in self:
            if expense.amount <= 0:
                raise ValidationError(_("Le montant doit être positif."))
    
    @api.constrains('date', 'vehicle_id')
    def _check_date_valid(self):
        """Ensure date is not in future and not before vehicle acquisition."""
        for expense in self:
            if expense.date > fields.Date.context_today(self):
                raise ValidationError(_("La date ne peut pas être dans le futur."))
            
            if expense.vehicle_id.acquisition_date:
                if expense.date < expense.vehicle_id.acquisition_date:
                    raise ValidationError(_(
                        "La date du frais (%(expense_date)s) ne peut pas être antérieure "
                        "à la date d'acquisition du véhicule (%(acquisition_date)s).",
                        expense_date=expense.date.strftime('%d/%m/%Y'),
                        acquisition_date=expense.vehicle_id.acquisition_date.strftime('%d/%m/%Y'),
                    ))
    
    # =========================================================================
    # ONCHANGE
    # =========================================================================
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set default date to vehicle acquisition date if available."""
        if self.vehicle_id and self.vehicle_id.acquisition_date:
            if not self.date or self.date < self.vehicle_id.acquisition_date:
                self.date = self.vehicle_id.acquisition_date
    
    @api.onchange('expense_type_id')
    def _onchange_expense_type_id(self):
        """Set default vendor from expense type if available."""
        if self.expense_type_id and self.expense_type_id.default_vendor_id:
            self.vendor_id = self.expense_type_id.default_vendor_id
    
    # =========================================================================
    # ACTIONS
    # =========================================================================
    
    def action_confirm(self):
        """Confirm the expense."""
        for expense in self:
            if expense.state != 'draft':
                raise UserError(_("Seuls les frais en brouillon peuvent être confirmés."))
        self.write({'state': 'confirmed'})
    
    def action_cancel(self):
        """Cancel the expense."""
        for expense in self:
            if expense.state == 'cancelled':
                raise UserError(_("Ce frais est déjà annulé."))
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        """Reset to draft."""
        for expense in self:
            if expense.state != 'cancelled':
                raise UserError(_("Seuls les frais annulés peuvent être remis en brouillon."))
        self.write({'state': 'draft'})
    
    def action_view_attachments(self):
        """View attachments action."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pièces Jointes - %s') % self.name,
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }


class FleetVehicleReceptionExpenseType(models.Model):
    """Reception expense types master data."""
    
    _name = 'fleet.vehicle.reception.expense.type'
    _description = 'Type de Frais de Réception'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
    )
    
    code = fields.Char(
        string='Code',
        help="Code technique unique pour ce type de frais.",
    )
    
    sequence = fields.Integer(
        string='Séquence',
        default=10,
    )
    
    description = fields.Text(
        string='Description',
        translate=True,
    )
    
    default_vendor_id = fields.Many2one(
        'res.partner',
        string='Fournisseur par Défaut',
        domain="[('supplier_rank', '>', 0)]",
        help="Fournisseur utilisé par défaut pour ce type de frais.",
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
    )
    
    expense_count = fields.Integer(
        string='Nb Frais',
        compute='_compute_expense_count',
    )
    
    @api.depends('active')
    def _compute_expense_count(self):
        """Compute number of expenses for this type."""
        Expense = self.env['fleet.vehicle.reception.expense']
        for expense_type in self:
            expense_type.expense_count = Expense.search_count([
                ('expense_type_id', '=', expense_type.id),
            ])
    
    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', "Le code doit être unique."),
        ('name_uniq', 'UNIQUE(name)', "Le nom doit être unique."),
    ]


class FleetVehicle(models.Model):
    """Extend vehicle with reception expenses."""
    
    _inherit = 'fleet.vehicle'
    
    reception_expense_ids = fields.One2many(
        'fleet.vehicle.reception.expense',
        'vehicle_id',
        string='Frais de Réception',
    )
    
    reception_expense_count = fields.Integer(
        string='Nb Frais Réception',
        compute='_compute_reception_expense_count',
    )
    
    total_reception_expenses = fields.Monetary(
        string='Total Frais Réception',
        compute='_compute_total_reception_expenses',
        currency_field='currency_id',
        help="Total des frais de réception confirmés pour ce véhicule.",
    )
    
    @api.depends('reception_expense_ids')
    def _compute_reception_expense_count(self):
        """Compute number of reception expenses."""
        for vehicle in self:
            vehicle.reception_expense_count = len(vehicle.reception_expense_ids)
    
    @api.depends('reception_expense_ids', 'reception_expense_ids.amount', 
                 'reception_expense_ids.state')
    def _compute_total_reception_expenses(self):
        """Compute total confirmed reception expenses."""
        for vehicle in self:
            confirmed_expenses = vehicle.reception_expense_ids.filtered(
                lambda e: e.state == 'confirmed'
            )
            vehicle.total_reception_expenses = sum(confirmed_expenses.mapped('amount'))
    
    def action_view_reception_expenses(self):
        """Action to view reception expenses."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Frais de Réception - %s') % self.name,
            'res_model': 'fleet.vehicle.reception.expense',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'default_date': self.acquisition_date or fields.Date.context_today(self),
            },
        }
