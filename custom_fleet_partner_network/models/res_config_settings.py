# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """
    Extension des paramètres de configuration pour le module fleet partner network.
    
    Phase 2 (TASK-008):
    - Délai d'alerte avant expiration des contrats
    - Assureur/garage/remorqueur par défaut
    - Configuration des notifications
    
    IMPORTANT: Tous les champs doivent être préfixés 'fleet_partner_' conformément à odoo19-python-conventions.md
    """
    _inherit = 'res.config.settings'

    # ========== ALERTES & NOTIFICATIONS ==========
    
    fleet_partner_alert_offset = fields.Integer(
        string='Délai d\'Alerte Contrat (jours)',
        default=30,
        config_parameter='custom_fleet_partner_network.alert_offset',
        help="Nombre de jours avant expiration pour déclencher une alerte (défaut: 30 jours)"
    )
    
    fleet_partner_enable_weekly_digest = fields.Boolean(
        string='Activer Digest Hebdomadaire',
        default=True,
        config_parameter='custom_fleet_partner_network.enable_weekly_digest',
        help="Envoyer un récapitulatif hebdomadaire des contrats et alertes"
    )
    
    fleet_partner_digest_day = fields.Selection(
        [
            ('0', 'Lundi'),
            ('1', 'Mardi'),
            ('2', 'Mercredi'),
            ('3', 'Jeudi'),
            ('4', 'Vendredi'),
        ],
        string='Jour du Digest',
        default='0',
        config_parameter='custom_fleet_partner_network.digest_day',
        help="Jour de la semaine pour l'envoi du digest"
    )
    
    fleet_partner_responsible_ids = fields.Many2many(
        'res.users',
        'fleet_partner_responsible_rel',
        'config_id',
        'user_id',
        string='Responsables Notifications',
        help="Utilisateurs qui recevront les alertes et digests des contrats partenaires"
    )
    
    # ========== PARTENAIRES PAR DÉFAUT ==========
    
    fleet_partner_default_insurer_id = fields.Many2one(
        'fleet.partner.profile',
        string='Assureur par Défaut',
        domain="[('partner_type', '=', 'assureur')]",
        config_parameter='custom_fleet_partner_network.default_insurer_id',
        help="Compagnie d'assurance proposée par défaut pour les nouveaux véhicules"
    )
    
    fleet_partner_default_garage_ids = fields.Many2many(
        'fleet.partner.profile',
        'fleet_partner_default_garage_rel',
        'config_id',
        'garage_id',
        string='Garages par Défaut',
        domain="[('partner_type', '=', 'garage')]",
        help="Garages proposés par défaut pour les nouveaux véhicules"
    )
    
    fleet_partner_default_tow_id = fields.Many2one(
        'fleet.partner.profile',
        string='Remorqueur par Défaut',
        domain="[('partner_type', '=', 'remorqueur')]",
        config_parameter='custom_fleet_partner_network.default_tow_id',
        help="Remorqueur proposé par défaut pour les interventions"
    )
    
    # ========== CONTRATS ==========
    
    fleet_partner_default_contract_duration = fields.Integer(
        string='Durée Contrat par Défaut (jours)',
        default=365,
        config_parameter='custom_fleet_partner_network.default_contract_duration',
        help="Durée standard d'un contrat (défaut: 365 jours / 1 an)"
    )
    
    fleet_partner_auto_expire_contracts = fields.Boolean(
        string='Expiration Automatique des Contrats',
        default=True,
        config_parameter='custom_fleet_partner_network.auto_expire_contracts',
        help="Marquer automatiquement les contrats comme expirés après leur date de fin"
    )
    
    fleet_partner_require_contract_approval = fields.Boolean(
        string='Approbation des Contrats Requise',
        default=False,
        config_parameter='custom_fleet_partner_network.require_contract_approval',
        help="Les contrats doivent être approuvés avant activation"
    )
    
    # ========== MÉTHODES ==========
    
    @api.onchange('fleet_partner_alert_offset')
    def _onchange_fleet_partner_alert_offset(self):
        """Valide que le délai d'alerte est positif."""
        if self.fleet_partner_alert_offset and self.fleet_partner_alert_offset < 1:
            return {
                'warning': {
                    'title': 'Valeur Invalide',
                    'message': 'Le délai d\'alerte doit être d\'au moins 1 jour.',
                }
            }
    
    @api.onchange('fleet_partner_default_contract_duration')
    def _onchange_fleet_partner_default_contract_duration(self):
        """Valide que la durée de contrat est positive."""
        if self.fleet_partner_default_contract_duration and self.fleet_partner_default_contract_duration < 1:
            return {
                'warning': {
                    'title': 'Valeur Invalide',
                    'message': 'La durée du contrat doit être d\'au moins 1 jour.',
                }
            }
    
    def set_values(self):
        """Sauvegarde les paramètres de configuration."""
        super().set_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        
        # Sauvegarder les Many2one et Many2many (car config_parameter ne gère que des strings)
        if self.fleet_partner_default_insurer_id:
            IrConfigParam.set_param(
                'custom_fleet_partner_network.default_insurer_id',
                self.fleet_partner_default_insurer_id.id
            )
        
        if self.fleet_partner_default_tow_id:
            IrConfigParam.set_param(
                'custom_fleet_partner_network.default_tow_id',
                self.fleet_partner_default_tow_id.id
            )
        
        # Sauvegarder les responsables (Many2many)
        if self.fleet_partner_responsible_ids:
            IrConfigParam.set_param(
                'custom_fleet_partner_network.responsible_ids',
                ','.join(str(uid) for uid in self.fleet_partner_responsible_ids.ids)
            )
        
        # Sauvegarder les garages par défaut (Many2many)
        if self.fleet_partner_default_garage_ids:
            IrConfigParam.set_param(
                'custom_fleet_partner_network.default_garage_ids',
                ','.join(str(gid) for gid in self.fleet_partner_default_garage_ids.ids)
            )
    
    @api.model
    def get_values(self):
        """Récupère les paramètres de configuration."""
        res = super().get_values()
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        
        # Récupérer l'assureur par défaut
        default_insurer_id = IrConfigParam.get_param('custom_fleet_partner_network.default_insurer_id')
        if default_insurer_id:
            res['fleet_partner_default_insurer_id'] = int(default_insurer_id)
        
        # Récupérer le remorqueur par défaut
        default_tow_id = IrConfigParam.get_param('custom_fleet_partner_network.default_tow_id')
        if default_tow_id:
            res['fleet_partner_default_tow_id'] = int(default_tow_id)
        
        # Récupérer les responsables
        responsible_ids_str = IrConfigParam.get_param('custom_fleet_partner_network.responsible_ids')
        if responsible_ids_str:
            res['fleet_partner_responsible_ids'] = [(6, 0, [int(uid) for uid in responsible_ids_str.split(',') if uid.strip()])]
        
        # Récupérer les garages par défaut
        default_garage_ids_str = IrConfigParam.get_param('custom_fleet_partner_network.default_garage_ids')
        if default_garage_ids_str:
            res['fleet_partner_default_garage_ids'] = [(6, 0, [int(gid) for gid in default_garage_ids_str.split(',') if gid.strip()])]
        
        return res
