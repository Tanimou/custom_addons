# -*- coding: utf-8 -*-
#############################################################################
#
#    Partenaire Succes Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Partenaire Succes(<https://www.partenairesucces.com>)
#    Author: Adama KONE
#
#############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class EmployeeCreditLimit(models.Model):
    _name = 'employee.credit.limit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Limite de crédits des employés'

    name = fields.Char(string='Nom', readonly=True, copy=False)
    partner_company_id = fields.Many2one(
        'res.partner',
        string='Entreprise cliente',
        required=True,
        tracking=True
    )
    start = fields.Datetime(
        string="Date de début",
        default=fields.Datetime.now,
        required=True,
        copy=False,
        tracking=True
    )
    end = fields.Datetime(string='Date de fin', copy=False, tracking=True)
    amount = fields.Float(string='Montant du crédit', required=True, tracking=True)
    total_amount_limit = fields.Float(
        string="Limite Crédit totale du partenaire",
        compute='_compute_total_amount_limit',
        store=False
    )
    count_child = fields.Integer(
        string="Nombre d'employés",
        compute='_compute_count_child'
    )
    amount_used = fields.Float(
        string='Montant consommé',
        compute='_compute_amount_used',
        store=False
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        required=True
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé')
    ], string='État', default='draft', required=True)
    note = fields.Text('Note')

    partner_ids = fields.One2many(
        'res.partner',
        'limit_id',
        compute='_compute_partner_company',
        string='Bénéficiaires',
        copy=False
    )

    line_ids = fields.One2many(
        'employee.credit.limit.line',
        'limit_id',
        string='Lignes de crédit',
        copy=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------

    @api.depends('partner_company_id')
    def _compute_partner_company(self):
        """Récupère tous les employés liés à l'entreprise cliente."""
        Partner = self.env['res.partner']
        for record in self:
            if record.partner_company_id:
                partners = Partner.search([
                    ('parent_id', '=', record.partner_company_id.id)
                ])
                record.partner_ids = partners
            else:
                record.partner_ids = False

    @api.depends('line_ids.amount_used')
    def _compute_amount_used(self):
        """Somme du montant utilisé sur toutes les lignes."""
        for record in self:
            record.amount_used = sum(record.line_ids.mapped('amount_used'))

    @api.depends('line_ids')
    def _compute_total_amount_limit(self):
        """Somme des montants définis sur toutes les lignes."""
        for record in self:
            record.total_amount_limit = sum(record.line_ids.mapped('amount'))

    @api.depends('partner_company_id')
    def _compute_count_child(self):
        """Compte le nombre d'employés liés à la société."""
        Partner = self.env['res.partner']
        for record in self:
            record.count_child = Partner.search_count([
                ('parent_id', '=', record.partner_company_id.id)
            ])

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------

    def unlink(self):
        """Empêche la suppression si le crédit n'est pas en brouillon."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Vous ne pouvez supprimer que les crédits à l'état Brouillon."))
        return super().unlink()

    def action_done(self):
        """Passe à l'état 'En cours' après génération."""
        for record in self:
            if not record.line_ids:
                raise UserError(_("Vous devez d'abord créer les lignes de crédit avant de valider."))
            record.state = 'in_progress'

    def action_close(self):
        """Clôture le crédit."""
        self.write({'state': 'done'})

    # -------------------------------------------------------------------------
    # GÉNÉRATION DES CRÉDITS
    # -------------------------------------------------------------------------

    def action_generate_credits_with_lines(self):
        """Action unifiée pour créer les crédits et générer toutes les lignes (optimisée et sécurisée)."""
        today = fields.Date.today()
        start_date = today.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - relativedelta(days=1)

        months_fr = {
            1: 'JANVIER', 2: 'FÉVRIER', 3: 'MARS', 4: 'AVRIL',
            5: 'MAI', 6: 'JUIN', 7: 'JUILLET', 8: 'AOÛT',
            9: 'SEPTEMBRE', 10: 'OCTOBRE', 11: 'NOVEMBRE', 12: 'DÉCEMBRE'
        }

        month_name = months_fr[start_date.month]
        year = start_date.year

        Credit = self.env['employee.credit.limit']
        existing_credits = Credit.browse()

        for record in self:
            if not record.partner_company_id:
                raise UserError(_(
                    "Impossible de générer le crédit pour '%s' : le champ 'Entreprise cliente' n'est pas renseigné."
                ) % (record.name or record.id))
            if record.amount <= 0:
                raise UserError(_(
                    "Impossible de générer le crédit pour '%s' : le champ 'Montant du crédit' doit avoir une valeur positive."
                ) % (record.name or record.id)) 

            company = record.partner_company_id
            credit_name = f"CREDIT/{month_name}/{year}/{company.name.upper()}"

            existing_credit = Credit.search([('name', '=', credit_name)], limit=1)
            if existing_credit:
                existing_credits |= existing_credit
                continue
            record.write(
                {'name': credit_name,
                 'partner_company_id': company.id,
                 'amount': record.amount,
                 'start': start_date,
                 'end': end_date,
                }
            )
            record._create_lines_for_credit(record)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _create_lines_for_credit(self, food_credit):
        """Créer les lignes pour un crédit spécifique."""
        if food_credit.line_ids:
            food_credit.line_ids.unlink()

        partners = self.env['res.partner'].search([
            ('parent_id', '=', food_credit.partner_company_id.id),
            ('active', '=', True),
        ])
        if not partners:
            return 0

        vals_list = [{
            'partner_id': partner.id,
            'amount': food_credit.amount,
            'start': food_credit.start,
            'end': food_credit.end,
            'limit_id': food_credit.id,
            'partner_company_id': food_credit.partner_company_id.id,
        } for partner in partners]

        self.env['employee.credit.limit.line'].create(vals_list)
        return len(vals_list)


class EmployeeCreditLimitLine(models.Model):
    _name = 'employee.credit.limit.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Lignes de limite de credit des employés'

    partner_id = fields.Many2one(
        'res.partner',
        'Client'
    ) 
    partner_name = fields.Char(related='partner_id.name', string='Nom du client', store=True)
    amount = fields.Float('Montant du crédit mensuel', default=0)
    start = fields.Datetime(string="Date de debut", default=fields.Datetime.now, required=True, copy=False)
    end = fields.Datetime(string='Date de fin', copy=False, required=True)
    limit_id = fields.Many2one(
        'employee.credit.limit',
        'Limite de credit employés'
    )
    solde = fields.Float('Solde disponible', default=0, compute='compute_solde')
    amount_used = fields.Float('Montants consommés')
    partner_company_id = fields.Many2one('res.partner', 
                                         string='Entreprise cliente', 
                                         required=True)
    state = fields.Selection(related='limit_id.state', string='État', store=True)


    @api.onchange('amount', 'amount_used')
    def compute_solde(self):
        for record in self:
            record.solde = record.amount - record.amount_used