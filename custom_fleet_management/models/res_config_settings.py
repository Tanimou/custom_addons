# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    """
    Extension des paramètres de configuration pour le module Fleet Management.
    
    Ajoute des options de configuration pour:
    - Alertes J-30
    - Synchronisation calendrier
    - Blocage des conflits
    - Responsables alertes
    """
    _inherit = 'res.config.settings'

    # ========== ALERTES & NOTIFICATIONS ==========
    
    fleet_alert_offset_days = fields.Integer(
        string='Délai Alertes (jours)',
        default=30,
        config_parameter='fleet.alert_offset_days',
        help="Nombre de jours avant expiration pour déclencher les alertes (défaut: 30 jours)"
    )
    
    fleet_weekly_alert_enabled = fields.Boolean(
        string='Activer Digest Hebdomadaire',
        default=True,
        config_parameter='fleet.weekly_alert_enabled',
        help="Envoyer un récapitulatif hebdomadaire des alertes par email"
    )
    
    fleet_responsible_ids = fields.Many2many(
        'res.users',
        'fleet_config_responsible_rel',
        'config_id',
        'user_id',
        string='Responsables Alertes',
        help="Utilisateurs qui recevront les alertes et digests hebdomadaires"
    )
    
    # ========== CALENDRIER ==========
    
    fleet_create_calendar_events = fields.Boolean(
        string='Créer Événements Calendrier',
        default=False,
        config_parameter='fleet.create_calendar_events',
        help="Créer automatiquement un événement dans le calendrier Odoo pour chaque mission assignée"
    )
    
    # ========== CONFLITS ==========
    
    fleet_block_conflicting_missions = fields.Boolean(
        string='Bloquer Missions en Conflit',
        default=False,
        config_parameter='fleet.block_conflicting_missions',
        help="Empêcher l'approbation de missions avec conflits d'affectation (véhicule ou conducteur déjà assigné)"
    )
    
    # ========== KILOMÉTRAGE ==========
    
    fleet_odometer_alert_threshold = fields.Integer(
        string='Seuil Alerte Kilométrage',
        default=10000,
        config_parameter='fleet.odometer_alert_threshold',
        help="Déclencher une alerte tous les X kilomètres pour rappel entretien périodique"
    )
    
    # ========== MISSION DEFAULTS ==========
    
    fleet_default_mission_type = fields.Selection(
        [
            ('urban', 'Course Urbaine'),
            ('intercity', 'Mission Interurbaine'),
            ('delivery', 'Livraison'),
            ('maintenance', 'Déplacement Maintenance'),
            ('administrative', 'Mission Administrative'),
            ('other', 'Autre'),
        ],
        string='Type Mission par Défaut',
        default='urban',
        config_parameter='fleet.default_mission_type',
        help="Type de mission prérempli lors de la création"
    )
    
    # ========== MÉTHODES ==========
    
    @api.model
    def get_values(self):
        """Récupère les valeurs de configuration."""
        res = super(ResConfigSettings, self).get_values()
        
        # Récupérer les responsables depuis ir.config_parameter
        responsible_ids_str = self.env['ir.config_parameter'].sudo().get_param('fleet.responsible_ids', default='')
        responsible_ids = [int(id) for id in responsible_ids_str.split(',') if id]
        
        res.update(
            fleet_responsible_ids=[(6, 0, responsible_ids)],
        )
        
        return res
    
    def set_values(self):
        """Enregistre les valeurs de configuration."""
        super(ResConfigSettings, self).set_values()
        
        # Sauvegarder les responsables dans ir.config_parameter
        responsible_ids_str = ','.join(str(id) for id in self.fleet_responsible_ids.ids)
        self.env['ir.config_parameter'].sudo().set_param('fleet.responsible_ids', responsible_ids_str)
