from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time
import re
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicketInherit(models.Model):
    _inherit = 'helpdesk.ticket'


    type_work = fields.Selection(
        [
            ('repair', 'Réparation'), 
            ('construction', 'Construction'), 
            ('development', 'Aménagement'),
            ('other', 'Autre'),
        ], string='Type de travaux', 
        default='repair', 
        required=True
    )

    state = fields.Selection(
        [
            ('draft', 'Nouveau'), 
            ('progress', 'En cours'), 
            ('pending', 'En attente'),
            ('resolved', 'Resolu'),
            ('cancel', 'Annuler'),
        ], string='statut', 
        default='draft', 
        compute="_compute_state",
        store=True
    )

    office_id = fields.Many2one(
        'office.room.booking',
        string='Bureau',
    )

    room_id = fields.Many2one(
        'room.room',
        string='Salle',
    )

    purchase_ids = fields.One2many(
        'purchase.order',
        'helpdesk_id',
        string="Bon d'achat",
        readonly=True,
    )

    equipment_ids = fields.Many2many(
        comodel_name='product.template',
        string='Equipements',
    )

    date_intervention = fields.Datetime(
        string="Date souhaitée d’intervention",
    )

    purchase_order_count = fields.Integer(
        string='Nombre d\'achats',
        compute='_compute_purchase_order_count'
    )

    currency_id = fields.Many2one(related='company_id.currency_id')
    purchase_amount = fields.Monetary(
        string='Montant total des achats',
        compute='_compute_purchase_order_count',
        currency_field='currency_id'
    )


    def action_validate(self):
        if not self.user_id:
            raise ValidationError(
                _("Vous devez assigner un utilisateur avant de valider"))
        self.write({
            'stage_id': self.env.ref('helpdesk.stage_in_progress').id
        })

   
    def action_cancel(self):
        self.write({
            'stage_id': self.env.ref('helpdesk.stage_cancelled').id
        })

    def action_draft(self):
        self.write({
            'stage_id': self.env.ref('helpdesk.stage_new').id
        })

    def action_close (self):
        self.write({
            'stage_id': self.env.ref('helpdesk.stage_solved').id
        })

    def action_send_back(self):
        self.write({
            'stage_id': self.env.ref('helpdesk.stage_on_hold').id
        })

    @api.depends('stage_id')
    def _compute_state(self):
        """Met à jour le state en fonction du stage_id"""
        for rec in self:
            if not rec.stage_id:
                rec.state = 'draft'
                continue
            
            stage_draft = self.env.ref('helpdesk.stage_new', raise_if_not_found=False)
            stage_progress = self.env.ref('helpdesk.stage_in_progress', raise_if_not_found=False)
            stage_pending = self.env.ref('helpdesk.stage_on_hold', raise_if_not_found=False)
            stage_solved = self.env.ref('helpdesk.stage_solved', raise_if_not_found=False)
            stage_cancel = self.env.ref('helpdesk.stage_cancelled', raise_if_not_found=False)
            
            if rec.stage_id == stage_draft:
                rec.state = 'draft'
            elif rec.stage_id == stage_progress:
                rec.state = 'progress'
            elif rec.stage_id == stage_pending:
                rec.state = 'pending'
            elif rec.stage_id == stage_solved:
                rec.state = 'resolved'
            elif rec.stage_id == stage_cancel:
                rec.state = 'cancel'
            else:
                rec.state = 'draft'


    @api.depends('purchase_ids')
    def _compute_purchase_order_count(self):
        """Calcule le nombre de commandes d'achat liées au ticket"""
        for ticket in self:
            ticket.purchase_order_count = len(ticket.purchase_ids)
            ticket.purchase_amount = sum(ticket.purchase_ids.mapped('amount_total'))


    def action_create_purchase_order(self):
        """
        Ouvre une nouvelle commande d'achat lie au ticket 
        """
        self.ensure_one()
        
        action = {
            'name': 'Nouvelle commande d\'achat',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_helpdesk_id': self.id,
            }
        }
        return action
    
    
    def action_view_purchase_orders(self):
        """
        Bouton : Ouvre la vue des achats avec les lignes de purchase_ids
        """
        self.ensure_one()
        purchase_ids = self.purchase_ids.ids
        
        action = {
            'name': 'Commandes d\'achat',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'domain': [('id', 'in', purchase_ids)],
            'context': {
                'default_helpdesk_id': self.id,
            }
        }
        if self.purchase_order_count == 0:
            action['view_mode'] = 'form'
            action['target'] = 'current'
        elif self.purchase_order_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = purchase_ids[0]
        else:
            action['view_mode'] = 'list,form'
        
        return action
    