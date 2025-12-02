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

    # ========== NOTIFICATIONS ==========
    
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
    
    # ========== MÉTHODES ==========
    
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
        
        # Récupérer les garages par défaut
        default_garage_ids_str = IrConfigParam.get_param('custom_fleet_partner_network.default_garage_ids')
        if default_garage_ids_str:
            res['fleet_partner_default_garage_ids'] = [(6, 0, [int(gid) for gid in default_garage_ids_str.split(',') if gid.strip()])]
        
        return res
