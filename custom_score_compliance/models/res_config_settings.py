# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """SCORE Compliance configuration settings.
    
    All fields are module-prefixed with 'custom_score_compliance_'.
    All config_parameter keys are namespaced with 'custom_score_compliance.'.
    
    Default enforcement behavior (per spec clarification):
    - Block on submit: True (mission cannot be submitted with expired critical docs)
    - Block on start: True (mission cannot be started with expired critical docs)
    - Block on create: False (draft missions allowed with warning)
    - Warn on vehicle change: True (show warning when vehicle has expired docs)
    """
    _inherit = 'res.config.settings'

    # ==========================================================================
    # COMPLIANCE BLOCKING TOGGLES (FR-007a)
    # ==========================================================================
    
    custom_score_compliance_block_mission_on_submit = fields.Boolean(
        string="Bloquer la soumission de mission",
        help="Empêcher la soumission d'une mission si le véhicule a des documents critiques expirés.",
        config_parameter='custom_score_compliance.block_mission_on_submit',
        default=True,
    )
    
    custom_score_compliance_block_mission_on_start = fields.Boolean(
        string="Bloquer le démarrage de mission",
        help="Empêcher le démarrage d'une mission si le véhicule a des documents critiques expirés.",
        config_parameter='custom_score_compliance.block_mission_on_start',
        default=True,
    )
    
    custom_score_compliance_block_mission_on_create = fields.Boolean(
        string="Bloquer la création de mission",
        help="Empêcher la création d'une mission (même en brouillon) si le véhicule a des documents critiques expirés. "
             "Par défaut désactivé (les missions en brouillon sont autorisées avec un avertissement).",
        config_parameter='custom_score_compliance.block_mission_on_create',
        default=False,
    )
    
    custom_score_compliance_warn_on_vehicle_change = fields.Boolean(
        string="Avertir lors du changement de véhicule",
        help="Afficher un avertissement lors de la sélection d'un véhicule avec des documents expirés (critiques ou non).",
        config_parameter='custom_score_compliance.warn_on_vehicle_change',
        default=True,
    )
    
    # ==========================================================================
    # ALERT CONFIGURATION (FR-007)
    # ==========================================================================
    
    custom_score_compliance_alert_days_before_expiry = fields.Integer(
        string="Jours avant échéance pour alerte",
        help="Nombre de jours avant l'échéance d'un document pour déclencher une alerte (J-X). Par défaut: 30 jours.",
        config_parameter='custom_score_compliance.alert_days_before_expiry',
        default=30,
    )
    
    custom_score_compliance_enable_weekly_reminders = fields.Boolean(
        string="Activer les rappels hebdomadaires",
        help="Envoyer des rappels hebdomadaires pour les documents arrivant à échéance.",
        config_parameter='custom_score_compliance.enable_weekly_reminders',
        default=True,
    )
