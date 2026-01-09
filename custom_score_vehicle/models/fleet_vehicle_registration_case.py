# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T026-T027: Fleet Vehicle Registration Case model (FR-008)
Workflow: in_progress → validated OR rejected
Rejection requires rejection_reason (constraint).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FleetVehicleRegistrationCase(models.Model):
    """
    Registration case (dossier d'immatriculation) for a vehicle.
    
    Tracks the administrative process of vehicle registration/immatriculation
    with workflow states and rejection reason enforcement.
    """
    
    _name = 'fleet.vehicle.registration.case'
    _description = 'Dossier Immatriculation Véhicule'
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
        help="Référence unique du dossier d'immatriculation"
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help="Véhicule concerné par ce dossier d'immatriculation"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    
    # ==========================================================================
    # Workflow State
    # ==========================================================================
    
    state = fields.Selection(
        [
            ('in_progress', 'En cours'),
            ('validated', 'Validé'),
            ('rejected', 'Rejeté'),
        ],
        string='État',
        default='in_progress',
        required=True,
        tracking=True,
        copy=False,
        help="État du dossier d'immatriculation"
    )
    
    # ==========================================================================
    # Rejection Fields
    # ==========================================================================
    
    rejection_reason = fields.Text(
        string='Motif de Rejet',
        tracking=True,
        help="Motif obligatoire en cas de rejet du dossier"
    )
    
    rejected_by_id = fields.Many2one(
        'res.users',
        string='Rejeté par',
        readonly=True,
        tracking=True,
    )
    
    rejection_date = fields.Datetime(
        string='Date de Rejet',
        readonly=True,
        tracking=True,
    )
    
    # ==========================================================================
    # Validation Fields
    # ==========================================================================
    
    validated_by_id = fields.Many2one(
        'res.users',
        string='Validé par',
        readonly=True,
        tracking=True,
    )
    
    validation_date = fields.Datetime(
        string='Date de Validation',
        readonly=True,
        tracking=True,
    )
    
    # ==========================================================================
    # Additional Info
    # ==========================================================================
    
    requested_plate = fields.Char(
        string='Immatriculation Demandée',
        tracking=True,
        help="Numéro d'immatriculation demandé ou proposé"
    )
    
    assigned_plate = fields.Char(
        string='Immatriculation Attribuée',
        tracking=True,
        help="Numéro d'immatriculation finalement attribué"
    )
    
    notes = fields.Html(
        string='Notes',
        help="Notes et commentaires sur le dossier"
    )
    
    # ==========================================================================
    # Computed Fields
    # ==========================================================================
    
    can_validate = fields.Boolean(
        string='Peut Valider',
        compute='_compute_can_actions',
    )
    
    can_reject = fields.Boolean(
        string='Peut Rejeter',
        compute='_compute_can_actions',
    )
    
    @api.depends('state')
    def _compute_can_actions(self):
        for case in self:
            case.can_validate = case.state == 'in_progress'
            case.can_reject = case.state == 'in_progress'
    
    # ==========================================================================
    # Constraints
    # ==========================================================================
    
    @api.constrains('state', 'rejection_reason')
    def _check_rejection_reason_required(self):
        """Rejection reason is mandatory when state is 'rejected'."""
        for case in self:
            if case.state == 'rejected' and not case.rejection_reason:
                raise ValidationError(_(
                    "Le motif de rejet est obligatoire pour rejeter le dossier '%s'.",
                    case.name
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
                    'fleet.vehicle.registration.case'
                ) or _('Nouveau')
        
        records = super().create(vals_list)
        
        # Post creation message
        for record in records:
            record.message_post(
                body=_("Dossier d'immatriculation créé pour le véhicule %s", 
                       record.vehicle_id.display_name),
                subject=_("Nouveau Dossier Immatriculation")
            )
        
        return records
    
    # ==========================================================================
    # Action Methods (Workflow Transitions)
    # ==========================================================================
    
    def action_validate(self):
        """
        Validate the registration case.
        Only allowed from 'in_progress' state.
        """
        for case in self:
            if case.state != 'in_progress':
                raise UserError(_(
                    "Le dossier '%s' ne peut pas être validé car il n'est pas en cours.",
                    case.name
                ))
            
            case.write({
                'state': 'validated',
                'validated_by_id': self.env.uid,
                'validation_date': fields.Datetime.now(),
            })
            
            # Update vehicle plate if assigned
            if case.assigned_plate and case.vehicle_id:
                case.vehicle_id.license_plate = case.assigned_plate
            
            case.message_post(
                body=_("Dossier validé par %s", self.env.user.display_name),
                subject=_("Dossier Validé")
            )
        
        return True
    
    def action_reject(self):
        """
        Reject the registration case.
        Only allowed from 'in_progress' state.
        Requires rejection_reason to be set.
        """
        for case in self:
            if case.state != 'in_progress':
                raise UserError(_(
                    "Le dossier '%s' ne peut pas être rejeté car il n'est pas en cours.",
                    case.name
                ))
            
            # Check rejection reason before state change
            if not case.rejection_reason or not case.rejection_reason.strip():
                raise ValidationError(_(
                    "Veuillez saisir un motif de rejet avant de rejeter le dossier '%s'.",
                    case.name
                ))
            
            case.write({
                'state': 'rejected',
                'rejected_by_id': self.env.uid,
                'rejection_date': fields.Datetime.now(),
            })
            
            case.message_post(
                body=_("Dossier rejeté par %s. Motif: %s", 
                       self.env.user.display_name, case.rejection_reason),
                subject=_("Dossier Rejeté")
            )
        
        return True
    
    def action_reset_to_in_progress(self):
        """
        Reset a validated/rejected case back to in_progress.
        Typically for admin use only.
        """
        for case in self:
            if case.state == 'in_progress':
                raise UserError(_(
                    "Le dossier '%s' est déjà en cours.",
                    case.name
                ))
            
            case.write({
                'state': 'in_progress',
                'validated_by_id': False,
                'validation_date': False,
                'rejected_by_id': False,
                'rejection_date': False,
                # Keep rejection_reason for history
            })
            
            case.message_post(
                body=_("Dossier remis en cours par %s", self.env.user.display_name),
                subject=_("Dossier Réouvert")
            )
        
        return True
