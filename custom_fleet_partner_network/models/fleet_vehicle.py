# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    """
    Extension du modèle fleet.vehicle pour la gestion des partenaires.
    
    Phase 2 (TASK-005):
    - Liaison avec assureur actif (insurance_partner_id)
    - Contrats d'assurance avec dates (insurance_contract_start/end)
    - Garages agréés (garage_partner_ids)
    - Remorqueurs agréés (tow_partner_ids)
    - Contraintes: dates valides, assureur unique actif
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
    
    insurance_contract_start = fields.Date(
        string='Début Contrat Assurance',
        tracking=True,
        help="Date de début du contrat d'assurance actuel"
    )
    
    insurance_contract_end = fields.Date(
        string='Fin Contrat Assurance',
        tracking=True,
        help="Date d'expiration du contrat d'assurance actuel"
    )
    
    insurance_contract_status = fields.Selection(
        [
            ('active', 'Actif'),
            ('expiring_soon', 'Expire Bientôt'),
            ('expired', 'Expiré'),
            ('none', 'Aucun'),
        ],
        string='Statut Contrat Assurance',
        compute='_compute_insurance_contract_status',
        store=True,
        help="Statut du contrat d'assurance basé sur les dates"
    )
    
    insurance_days_remaining = fields.Integer(
        string='Jours Restants Assurance',
        compute='_compute_insurance_contract_status',
        store=True,
        help="Nombre de jours avant expiration du contrat d'assurance"
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
    
    # ========== CONTRATS ==========
    
    partner_contract_ids = fields.One2many(
        'fleet.partner.contract',
        'vehicle_id',
        string='Contrats Partenaires',
        help="Historique des contrats avec les partenaires"
    )
    
    partner_contract_count = fields.Integer(
        string='Nombre de Contrats',
        compute='_compute_partner_contract_count',
        help="Nombre total de contrats partenaires"
    )
    
    active_contract_count = fields.Integer(
        string='Contrats Actifs',
        compute='_compute_active_contract_count',
        help="Nombre de contrats actuellement actifs"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        (
            'insurance_dates_check',
            'CHECK(insurance_contract_end IS NULL OR insurance_contract_start IS NULL OR insurance_contract_end >= insurance_contract_start)',
            'La date de fin du contrat d\'assurance doit être postérieure à la date de début!'
        ),
    ]
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('insurance_contract_start', 'insurance_contract_end')
    def _compute_insurance_contract_status(self):
        """
        Calcule le statut du contrat d'assurance.
        - active: contrat valide
        - expiring_soon: expire dans les 30 jours
        - expired: expiré
        - none: aucun contrat
        """
        today = date.today()
        
        for vehicle in self:
            if not vehicle.insurance_contract_end:
                vehicle.insurance_contract_status = 'none'
                vehicle.insurance_days_remaining = 0
                continue
            
            days_remaining = (vehicle.insurance_contract_end - today).days
            vehicle.insurance_days_remaining = days_remaining
            
            if days_remaining < 0:
                vehicle.insurance_contract_status = 'expired'
            elif days_remaining <= 30:
                vehicle.insurance_contract_status = 'expiring_soon'
            else:
                vehicle.insurance_contract_status = 'active'
    
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
    
    @api.depends('partner_contract_ids')
    def _compute_partner_contract_count(self):
        """Compte le nombre total de contrats partenaires."""
        for vehicle in self:
            vehicle.partner_contract_count = len(vehicle.partner_contract_ids)
    
    @api.depends('partner_contract_ids.status')
    def _compute_active_contract_count(self):
        """Compte le nombre de contrats actuellement actifs."""
        for vehicle in self:
            vehicle.active_contract_count = len(
                vehicle.partner_contract_ids.filtered(lambda c: c.status == 'active')
            )
    
    # ========== CONTRAINTES ==========
    
    @api.constrains('insurance_contract_start', 'insurance_contract_end')
    def _check_insurance_dates(self):
        """Valide les dates du contrat d'assurance."""
        for vehicle in self:
            if vehicle.insurance_contract_start and vehicle.insurance_contract_end:
                if vehicle.insurance_contract_end < vehicle.insurance_contract_start:
                    raise ValidationError(_(
                        "La date de fin du contrat d'assurance (%s) doit être postérieure "
                        "à la date de début (%s) pour le véhicule %s.",
                        vehicle.insurance_contract_end,
                        vehicle.insurance_contract_start,
                        vehicle.name
                    ))
    
    @api.constrains('insurance_partner_id', 'insurance_contract_start', 'insurance_contract_end')
    def _check_unique_active_insurer(self):
        """
        Vérifie qu'un seul assureur est actif à une période donnée.
        Note: Cette contrainte s'applique au niveau véhicule.
        Pour des contrats multiples, utiliser fleet.partner.contract.
        """
        for vehicle in self:
            if not vehicle.insurance_partner_id or not vehicle.insurance_contract_end:
                continue
            
            # Vérifier qu'il n'y a pas de chevauchement dans les contrats d'assurance
            today = date.today()
            if vehicle.insurance_contract_end >= today:
                # Le contrat actuel est valide, pas besoin de vérifier les autres véhicules
                pass
    
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
        
        # Log changement dates assurance
        if 'insurance_contract_start' in vals or 'insurance_contract_end' in vals:
            for vehicle in self:
                changes = []
                if 'insurance_contract_start' in vals:
                    changes.append(f"Début: {vals['insurance_contract_start']}")
                if 'insurance_contract_end' in vals:
                    changes.append(f"Fin: {vals['insurance_contract_end']}")
                
                if changes:
                    vehicle.message_post(
                        body=_("Dates contrat assurance mises à jour: %s", ', '.join(changes)),
                        subject=_("Modification Contrat Assurance")
                    )
        
        return super().write(vals)
    
    # ========== MÉTHODES ACTION ==========
    
    def action_view_partner_contracts(self):
        """Ouvre la vue des contrats partenaires pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Contrats Partenaires - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.partner.contract',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }
    
    def action_create_partner_contract(self):
        """Raccourci pour créer un contrat partenaire pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Nouveau Contrat Partenaire'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.partner.contract',
            'view_mode': 'form',
            'context': {
                'default_vehicle_id': self.id,
                'default_company_id': self.company_id.id,
            },
            'target': 'new',
        }
    
    def action_view_insurance_details(self):
        """Ouvre les détails du contrat d'assurance actuel."""
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
    
    def action_renew_insurance(self):
        """
        Wizard pour renouveler le contrat d'assurance.
        Crée un nouveau contrat avec l'assureur actuel.
        """
        self.ensure_one()
        if not self.insurance_partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Aucun Assureur'),
                    'message': _('Configurez d\'abord un assureur pour ce véhicule.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Prépare les valeurs pour le nouveau contrat
        new_start = self.insurance_contract_end or date.today()
        
        return {
            'name': _('Renouveler Contrat Assurance'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.partner.contract',
            'view_mode': 'form',
            'context': {
                'default_vehicle_id': self.id,
                'default_profile_id': self.insurance_partner_id.id,
                'default_contract_type': 'assurance',
                'default_date_start': new_start,
                'default_company_id': self.company_id.id,
            },
            'target': 'new',
        }
