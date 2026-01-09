# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T029: Fleet Vehicle Transfer model (FR-016)
Workflow: draft → confirmed → validated → delivered (or cancelled)
Validation required before delivery.
Updates vehicle current_location_id on delivery.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FleetVehicleTransfer(models.Model):
    """
    Vehicle transfer between locations/sites.
    
    Tracks the movement of vehicles between stock locations with 
    a validation workflow to ensure proper handoff.
    """
    
    _name = 'fleet.vehicle.transfer'
    _description = 'Transfert Véhicule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'
    
    # ==========================================================================
    # Main Fields
    # ==========================================================================
    
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('Nouveau'),
        help="Référence unique du transfert"
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        help="Véhicule à transférer"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    
    # ==========================================================================
    # Location Fields
    # ==========================================================================
    
    location_src_id = fields.Many2one(
        'stock.location',
        string='Emplacement Source',
        required=True,
        tracking=True,
        domain="[('usage', '=', 'internal')]",
        help="Emplacement de départ du véhicule"
    )
    
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Emplacement Destination',
        required=True,
        tracking=True,
        domain="[('usage', '=', 'internal')]",
        help="Emplacement d'arrivée du véhicule"
    )
    
    # ==========================================================================
    # Workflow State
    # ==========================================================================
    
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('confirmed', 'Confirmé'),
            ('validated', 'Validé'),
            ('delivered', 'Livré'),
            ('cancelled', 'Annulé'),
        ],
        string='État',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        help="État du transfert"
    )
    
    # ==========================================================================
    # Date/Time Fields
    # ==========================================================================
    
    date_planned = fields.Datetime(
        string='Date Prévue',
        default=fields.Datetime.now,
        tracking=True,
        help="Date prévue pour le transfert"
    )
    
    date_confirmed = fields.Datetime(
        string='Date Confirmation',
        readonly=True,
        tracking=True,
    )
    
    date_validated = fields.Datetime(
        string='Date Validation',
        readonly=True,
        tracking=True,
    )
    
    date_delivered = fields.Datetime(
        string='Date Livraison',
        readonly=True,
        tracking=True,
    )
    
    # ==========================================================================
    # Responsible Users
    # ==========================================================================
    
    confirmed_by_id = fields.Many2one(
        'res.users',
        string='Confirmé par',
        readonly=True,
        tracking=True,
    )
    
    validated_by_id = fields.Many2one(
        'res.users',
        string='Validé par',
        readonly=True,
        tracking=True,
    )
    
    delivered_by_id = fields.Many2one(
        'res.users',
        string='Livré par',
        readonly=True,
        tracking=True,
    )
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
        help="Personne responsable de ce transfert"
    )
    
    # ==========================================================================
    # Additional Info
    # ==========================================================================
    
    reason = fields.Text(
        string='Motif du Transfert',
        tracking=True,
        help="Raison ou justification du transfert"
    )
    
    notes = fields.Html(
        string='Notes',
        help="Notes et commentaires sur le transfert"
    )
    
    # ==========================================================================
    # Computed Fields
    # ==========================================================================
    
    can_confirm = fields.Boolean(
        string='Peut Confirmer',
        compute='_compute_can_actions',
    )
    
    can_validate = fields.Boolean(
        string='Peut Valider',
        compute='_compute_can_actions',
    )
    
    can_deliver = fields.Boolean(
        string='Peut Livrer',
        compute='_compute_can_actions',
    )
    
    can_cancel = fields.Boolean(
        string='Peut Annuler',
        compute='_compute_can_actions',
    )
    
    @api.depends('state')
    def _compute_can_actions(self):
        for transfer in self:
            transfer.can_confirm = transfer.state == 'draft'
            transfer.can_validate = transfer.state == 'confirmed'
            transfer.can_deliver = transfer.state == 'validated'
            transfer.can_cancel = transfer.state in ('draft', 'confirmed')
    
    # ==========================================================================
    # Constraints
    # ==========================================================================
    
    @api.constrains('location_src_id', 'location_dest_id')
    def _check_different_locations(self):
        """Source and destination locations must be different."""
        for transfer in self:
            if transfer.location_src_id == transfer.location_dest_id:
                raise ValidationError(_(
                    "L'emplacement source et destination doivent être différents "
                    "pour le transfert '%s'.",
                    transfer.name
                ))
    
    # ==========================================================================
    # CRUD Methods
    # ==========================================================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign sequence reference on create."""
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fleet.vehicle.transfer'
                ) or _('Nouveau')
        
        records = super().create(vals_list)
        
        # Post creation message
        for record in records:
            record.message_post(
                body=_("Transfert créé: %s → %s",
                       record.location_src_id.display_name,
                       record.location_dest_id.display_name),
                subject=_("Nouveau Transfert Véhicule")
            )
        
        return records
    
    # ==========================================================================
    # Action Methods (Workflow Transitions)
    # ==========================================================================
    
    def action_confirm(self):
        """
        Confirm the transfer.
        Only allowed from 'draft' state.
        """
        for transfer in self:
            if transfer.state != 'draft':
                raise UserError(_(
                    "Le transfert '%s' ne peut pas être confirmé car il n'est pas en brouillon.",
                    transfer.name
                ))
            
            transfer.write({
                'state': 'confirmed',
                'confirmed_by_id': self.env.uid,
                'date_confirmed': fields.Datetime.now(),
            })
            
            transfer.message_post(
                body=_("Transfert confirmé par %s", self.env.user.display_name),
                subject=_("Transfert Confirmé")
            )
        
        return True
    
    def action_validate(self):
        """
        Validate the transfer.
        Only allowed from 'confirmed' state.
        """
        for transfer in self:
            if transfer.state != 'confirmed':
                raise UserError(_(
                    "Le transfert '%s' ne peut pas être validé car il n'est pas confirmé.",
                    transfer.name
                ))
            
            transfer.write({
                'state': 'validated',
                'validated_by_id': self.env.uid,
                'date_validated': fields.Datetime.now(),
            })
            
            transfer.message_post(
                body=_("Transfert validé par %s - Prêt pour livraison",
                       self.env.user.display_name),
                subject=_("Transfert Validé")
            )
        
        return True
    
    def action_deliver(self):
        """
        Mark the transfer as delivered.
        Only allowed from 'validated' state.
        Updates vehicle current_location_id.
        """
        for transfer in self:
            if transfer.state != 'validated':
                raise UserError(_(
                    "Le transfert '%s' ne peut pas être livré car il n'a pas été validé. "
                    "Veuillez d'abord valider le transfert.",
                    transfer.name
                ))
            
            transfer.write({
                'state': 'delivered',
                'delivered_by_id': self.env.uid,
                'date_delivered': fields.Datetime.now(),
            })
            
            # Update vehicle current location
            if transfer.vehicle_id:
                transfer.vehicle_id.current_location_id = transfer.location_dest_id.id
            
            transfer.message_post(
                body=_("Transfert livré par %s. Véhicule maintenant à: %s",
                       self.env.user.display_name,
                       transfer.location_dest_id.display_name),
                subject=_("Transfert Livré")
            )
        
        return True
    
    def action_cancel(self):
        """
        Cancel the transfer.
        Only allowed from 'draft' or 'confirmed' states.
        """
        for transfer in self:
            if transfer.state not in ('draft', 'confirmed'):
                raise UserError(_(
                    "Le transfert '%s' ne peut pas être annulé dans l'état '%s'. "
                    "Seuls les transferts en brouillon ou confirmés peuvent être annulés.",
                    transfer.name, transfer.state
                ))
            
            transfer.write({
                'state': 'cancelled',
            })
            
            transfer.message_post(
                body=_("Transfert annulé par %s", self.env.user.display_name),
                subject=_("Transfert Annulé")
            )
        
        return True
    
    def action_reset_to_draft(self):
        """
        Reset a cancelled transfer back to draft.
        Typically for admin use only.
        """
        for transfer in self:
            if transfer.state != 'cancelled':
                raise UserError(_(
                    "Seuls les transferts annulés peuvent être remis en brouillon."
                ))
            
            transfer.write({
                'state': 'draft',
                'confirmed_by_id': False,
                'date_confirmed': False,
                'validated_by_id': False,
                'date_validated': False,
            })
            
            transfer.message_post(
                body=_("Transfert remis en brouillon par %s", self.env.user.display_name),
                subject=_("Transfert Réouvert")
            )
        
        return True
