# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class FleetVehicle(models.Model):
    """
    Extension du modèle fleet.vehicle pour la gestion des partenaires.
    
    - Liaison avec assureur actif (insurance_partner_id)
    - Garages agréés (garage_partner_ids)
    - Remorqueurs agréés (tow_partner_ids)
    """
    _inherit = 'fleet.vehicle'

    # ========== ASSURANCE ==========
    
    insurance_partner_id = fields.Many2one(
        'fleet.partner.profile',
        string='Assureur',
        domain="[('partner_type', '=', 'assureur'), ('company_id', 'in', [company_id, False])]",
        tracking=True,
        help="Compagnie d'assurance actuellement active pour ce véhicule"
    )
    
    # ========== PARTENAIRES AGRÉÉS ==========
    
    garage_partner_ids = fields.Many2many(
        'fleet.partner.profile',
        'fleet_vehicle_garage_rel',
        'vehicle_id',
        'garage_id',
        string='Garages Agréés',
        domain="[('partner_type', '=', 'garage'), ('company_id', 'in', [company_id, False])]",
        help="Garages autorisés pour l'entretien de ce véhicule"
    )
    
    tow_partner_ids = fields.Many2many(
        'fleet.partner.profile',
        'fleet_vehicle_tow_rel',
        'vehicle_id',
        'tow_id',
        string='Remorqueurs Agréés',
        domain="[('partner_type', '=', 'remorqueur'), ('company_id', 'in', [company_id, False])]",
        help="Remorqueurs autorisés pour ce véhicule"
    )
    
    garage_count = fields.Integer(
        string='Nombre de Garages',
        compute='_compute_garage_count',
        help="Nombre de garages agréés"
    )
    
    tow_partner_count = fields.Integer(
        string='Nombre de Remorqueurs',
        compute='_compute_tow_partner_count',
        help="Nombre de remorqueurs agréés"
    )
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('garage_partner_ids')
    def _compute_garage_count(self):
        """Compte le nombre de garages agréés."""
        for vehicle in self:
            vehicle.garage_count = len(vehicle.garage_partner_ids)
    
    @api.depends('tow_partner_ids')
    def _compute_tow_partner_count(self):
        """Compte le nombre de remorqueurs agréés."""
        for vehicle in self:
            vehicle.tow_partner_count = len(vehicle.tow_partner_ids)
    
    # ========== MÉTHODES CRUD ==========
    
    def write(self, vals):
        """Log les changements de partenaires dans le chatter."""
        # Log changement assureur
        if 'insurance_partner_id' in vals:
            for vehicle in self:
                old_insurer = vehicle.insurance_partner_id.partner_id.name if vehicle.insurance_partner_id else 'Aucun'
                new_insurer_id = vals['insurance_partner_id']
                if new_insurer_id:
                    new_profile = self.env['fleet.partner.profile'].browse(new_insurer_id)
                    new_insurer = new_profile.partner_id.name
                else:
                    new_insurer = 'Aucun'
                
                if old_insurer != new_insurer:
                    vehicle.message_post(
                        body=_("Assureur modifié: %s → %s", old_insurer, new_insurer),
                        subject=_("Changement Assureur")
                    )
        
        return super().write(vals)
    
    # ========== MÉTHODES ACTION ==========
    
    def action_view_insurance_details(self):
        """Ouvre les détails de l'assureur actuel."""
        self.ensure_one()
        if not self.insurance_partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Aucun Assureur'),
                    'message': _('Ce véhicule n\'a pas d\'assureur configuré.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Assureur - %s', self.insurance_partner_id.partner_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.partner.profile',
            'res_id': self.insurance_partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
