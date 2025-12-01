# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FleetVehicle(models.Model):
    """
    Extension du modèle fleet.vehicle pour la gestion du parc automobile.
    
    Ajoute:
    - Code véhicule unique (VEH-####)
    - Suivi des échéances administratives (visite technique, assurance)
    - État administratif avec niveaux d'alerte
    - Liens vers missions et documents
    - Historique des affectations conducteurs
    """
    _inherit = 'fleet.vehicle'

    # ========== CHAMPS PRINCIPAUX ==========
    
    vehicle_code = fields.Char(
        string='Code Véhicule',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('Nouveau'),
        help="Identifiant unique du véhicule (ex: VEH-0001). Généré automatiquement."
    )
    
    # ========== ÉCHÉANCES ADMINISTRATIVES ==========
    
    date_prochaine_visite = fields.Date(
        string='Prochaine Visite Technique',
        tracking=True,
        help="Date de la prochaine visite technique obligatoire"
    )
    
    date_fin_assurance = fields.Date(
        string='Fin Assurance',
        tracking=True,
        help="Date d'expiration de l'assurance du véhicule"
    )
    
    date_fin_vignette = fields.Date(
        string='Fin Vignette',
        tracking=True,
        help="Date d'expiration de la vignette/taxe routière"
    )
    
    # ========== ÉTAT ADMINISTRATIF & ALERTES ==========
    
    administrative_state = fields.Selection(
        [
            ('ok', 'Conforme'),
            ('warning', 'Alerte (J-30)'),
            ('critical', 'Critique (Expiré)'),
        ],
        string='État Administratif',
        compute='_compute_administrative_state',
        store=True,
        help="État de conformité administrative du véhicule"
    )
    
    days_to_next_deadline = fields.Integer(
        string='Jours avant échéance',
        compute='_compute_administrative_state',
        store=True,
        help="Nombre de jours avant la prochaine échéance administrative"
    )
    
    next_deadline_summary = fields.Char(
        string='Prochaine Échéance',
        compute='_compute_administrative_state',
        store=True,
        help="Résumé de la prochaine échéance administrative"
    )
    
    has_expired_document = fields.Boolean(
        string='Document Expiré',
        compute='_compute_has_expired_document',
        store=True,
        help="Indique si au moins un document est expiré"
    )
    
    # ========== RELATIONS ==========
    
    mission_ids = fields.One2many(
        'fleet.mission',
        'vehicle_id',
        string='Missions',
        help="Missions associées à ce véhicule"
    )
    
    mission_count = fields.Integer(
        string='Nombre de Missions',
        compute='_compute_mission_count',
        help="Nombre total de missions pour ce véhicule"
    )
    
    document_ids = fields.One2many(
        'fleet.vehicle.document',
        'vehicle_id',
        string='Documents',
        help="Documents administratifs du véhicule"
    )
    
    document_count = fields.Integer(
        string='Nombre de Documents',
        compute='_compute_document_count',
        help="Nombre de documents attachés"
    )
    
    alert_count = fields.Integer(
        string='Nombre d\'Alertes',
        compute='_compute_alert_count',
        help="Nombre d'alertes actives sur ce véhicule"
    )
    
    # ========== DISPONIBILITÉ ==========
    
    is_available = fields.Boolean(
        string='Disponible',
        compute='_compute_is_available',
        store=True,
        help="Indique si le véhicule est actuellement en mission"
    )
    
    is_on_mission = fields.Boolean(
        string='En Mission',
        compute='_compute_is_on_mission',
        store=True,
        help="Indique si le véhicule est actuellement en mission"
    )
    
    current_mission_id = fields.Many2one(
        'fleet.mission',
        string='Mission en Cours',
        compute='_compute_current_mission',
        help="Mission actuellement en cours pour ce véhicule"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        ('vehicle_code_unique', 'UNIQUE(vehicle_code)', 
         'Le code véhicule doit être unique!'),
    ]
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('date_prochaine_visite', 'date_fin_assurance', 'date_fin_vignette', 'document_ids.expiry_date', 'document_ids.state')
    def _compute_administrative_state(self):
        """
        Calcule l'état administratif du véhicule en fonction des échéances.
        - Conforme: toutes les échéances > 30 jours
        - Alerte: au moins une échéance dans les 30 prochains jours
        - Critique: au moins une échéance expirée
        """
        today = date.today()
        warning_threshold = today + timedelta(days=30)
        
        for vehicle in self:
            deadlines = []
            
            # Collecte toutes les échéances
            if vehicle.date_prochaine_visite:
                deadlines.append(('Visite Technique', vehicle.date_prochaine_visite))
            if vehicle.date_fin_assurance:
                deadlines.append(('Assurance', vehicle.date_fin_assurance))
            if vehicle.date_fin_vignette:
                deadlines.append(('Vignette', vehicle.date_fin_vignette))
            
            # Ajoute les échéances des documents
            for doc in vehicle.document_ids:
                if doc.expiry_date and doc.state != 'valid':
                    deadlines.append((doc.document_type, doc.expiry_date))
            
            if not deadlines:
                vehicle.administrative_state = 'ok'
                vehicle.days_to_next_deadline = 0
                vehicle.next_deadline_summary = 'Aucune échéance enregistrée'
                continue
            
            # Trie par date et trouve la prochaine échéance
            deadlines.sort(key=lambda x: x[1])
            next_deadline_name, next_deadline_date = deadlines[0]
            days_diff = (next_deadline_date - today).days
            
            vehicle.days_to_next_deadline = days_diff
            vehicle.next_deadline_summary = f"{next_deadline_name}: {next_deadline_date.strftime('%d/%m/%Y')}"
            
            # Détermine l'état
            if days_diff < 0:
                vehicle.administrative_state = 'critical'
            elif days_diff <= 30:
                vehicle.administrative_state = 'warning'
            else:
                vehicle.administrative_state = 'ok'
    
    @api.depends('document_ids.state')
    def _compute_has_expired_document(self):
        """Vérifie si au moins un document est expiré."""
        for vehicle in self:
            vehicle.has_expired_document = any(
                doc.state == 'expired' for doc in vehicle.document_ids
            )
    
    @api.depends('mission_ids')
    def _compute_mission_count(self):
        """Compte le nombre de missions."""
        for vehicle in self:
            vehicle.mission_count = len(vehicle.mission_ids)
    
    @api.depends('document_ids')
    def _compute_document_count(self):
        """Compte le nombre de documents."""
        for vehicle in self:
            vehicle.document_count = len(vehicle.document_ids)
    
    @api.depends('administrative_state', 'has_expired_document')
    def _compute_alert_count(self):
        """Compte le nombre d'alertes actives."""
        for vehicle in self:
            count = 0
            if vehicle.administrative_state in ('warning', 'critical'):
                count += 1
            if vehicle.has_expired_document:
                count += 1
            vehicle.alert_count = count
    
    @api.depends('mission_ids.state', 'mission_ids.date_start', 'mission_ids.date_end', 'active')
    def _compute_is_available(self):
        """
        Vérifie si le véhicule est disponible.
        Un véhicule est indisponible s'il a une mission en cours (in_progress)
        ou une mission future approuvée.
        Note: la vérification de l'état maintenance est faite dans custom_fleet_maintenance.
        """
        today = date.today()
        for vehicle in self:
            # Véhicule non actif = non disponible
            if not vehicle.active:
                vehicle.is_available = False
                continue
            
            # Cherche missions actives ou futures
            active_missions = vehicle.mission_ids.filtered(
                lambda m: m.state in ('in_progress', 'approved') and
                         (not m.date_end or m.date_end.date() >= today)
            )
            
            vehicle.is_available = not active_missions
    

    
    @api.depends('mission_ids.state')
    def _compute_current_mission(self):
        """Trouve la mission actuellement en cours."""
        for vehicle in self:
            current = vehicle.mission_ids.filtered(lambda m: m.state == 'in_progress')
            vehicle.current_mission_id = current[:1] if current else False
    
    @api.depends('mission_ids.state')
    def _compute_is_on_mission(self):
        """Vérifie si le véhicule est actuellement en mission."""
        for vehicle in self:
            vehicle.is_on_mission = bool(
                vehicle.mission_ids.filtered(lambda m: m.state == 'in_progress')
            )
    
    # ========== MÉTHODES CRUD ==========
    
    @api.model_create_multi
    def create(self, vals_list):
        """
        Génère automatiquement le code véhicule lors de la création.
        Pattern: VEH-0001, VEH-0002, etc.
        """
        for vals in vals_list:
            if vals.get('vehicle_code', _('Nouveau')) == _('Nouveau'):
                vals['vehicle_code'] = self.env['ir.sequence'].next_by_code('fleet.vehicle.code') or _('Nouveau')
        
        vehicles = super().create(vals_list)
        
        # Log la création dans le chatter
        for vehicle in vehicles:
            vehicle.message_post(
                body=_("Véhicule créé avec le code %s", vehicle.vehicle_code),
                subject=_("Création Véhicule")
            )
        
        return vehicles
    
    def write(self, vals):
        """Logique métier lors de la mise à jour."""
        # Log les changements d'échéances importantes
        if any(key in vals for key in ['date_prochaine_visite', 'date_fin_assurance', 'date_fin_vignette']):
            for vehicle in self:
                changes = []
                if 'date_prochaine_visite' in vals:
                    changes.append(f"Visite technique: {vals['date_prochaine_visite']}")
                if 'date_fin_assurance' in vals:
                    changes.append(f"Assurance: {vals['date_fin_assurance']}")
                if 'date_fin_vignette' in vals:
                    changes.append(f"Vignette: {vals['date_fin_vignette']}")
                
                if changes:
                    vehicle.message_post(
                        body=_("Échéances mises à jour: %s", ', '.join(changes)),
                        subject=_("Modification Échéances")
                    )
        
        return super().write(vals)
    
    # ========== MÉTHODES ACTION ==========
    
    def action_view_missions(self):
        """Ouvre la vue des missions pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Missions - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.mission',
            'view_mode': 'list,form,kanban,calendar,gantt',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
    
    def action_view_documents(self):
        """Ouvre la vue des documents pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Documents - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
    
    def action_view_alerts(self):
        """Ouvre la vue des documents expirés/expirant pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Alertes Documents - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [
                ('vehicle_id', '=', self.id),
                ('state', 'in', ['expiring_soon', 'expired'])
            ],
            'context': {
                'default_vehicle_id': self.id,
                'search_default_expiring_soon': 1,
                'search_default_expired': 1,
            },
        }
    
    def action_create_mission(self):
        """Raccourci pour créer une mission pour ce véhicule."""
        self.ensure_one()
        return {
            'name': _('Nouvelle Mission'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.mission',
            'view_mode': 'form',
            'context': {
                'default_vehicle_id': self.id,
                'default_driver_id': self.driver_id.id if self.driver_id else False,
            },
            'target': 'new',
        }
    
    @api.model
    def action_send_weekly_digest(self):
        """
        Cron job: Envoi digest hebdomadaire (tous les lundis à 07:00)
        Envoie un rapport récapitulatif aux responsables du parc automobile.
        Envoie également des notifications internes et crée des activités.
        """
        ConfigParam = self.env['ir.config_parameter'].sudo()
        
        # Vérifier si le digest est activé
        weekly_alert_enabled = ConfigParam.get_param('fleet.weekly_alert_enabled', 'True') == 'True'
        if not weekly_alert_enabled:
            _logger.info("Weekly fleet digest is disabled")
            return
        
        # Récupérer les fleet managers
        fleet_manager_group = self.env.ref('custom_fleet_management.group_fleet_manager', raise_if_not_found=False)
        if not fleet_manager_group:
            _logger.warning("Fleet manager group not found")
            return
        
        fleet_managers = self.env['res.users'].search([
            ('group_ids', 'in', fleet_manager_group.ids),
            ('active', '=', True),
        ])
        
        if not fleet_managers:
            _logger.info("No fleet managers found for weekly digest")
            return
        
        # Collecter les statistiques pour toutes les sociétés
        today = date.today()
        week_ago = today - timedelta(days=7)
        week_ahead = today + timedelta(days=7)
        
        # Véhicules avec alertes
        vehicles_critical = self.search([
            ('administrative_state', '=', 'critical'),
            ('active', '=', True),
        ])
        vehicles_warning = self.search([
            ('administrative_state', '=', 'warning'),
            ('active', '=', True),
        ])
        
        # Missions en attente d'approbation
        missions_pending = self.env['fleet.mission'].search([
            ('state', '=', 'submitted'),
        ])
        
        # Missions terminées cette semaine
        missions_done = self.env['fleet.mission'].search([
            ('state', '=', 'done'),
            ('write_date', '>=', week_ago),
        ])
        
        # Missions à venir
        missions_upcoming = self.env['fleet.mission'].search([
            ('state', 'in', ['approved', 'in_progress']),
            ('date_start', '<=', week_ahead),
        ])
        
        # Documents expirant bientôt
        docs_expiring = self.env['fleet.vehicle.document'].search([
            ('state', '=', 'expiring_soon'),
        ])
        
        # Construire le message de notification
        notification_body = _(
            """
            <h3>📊 Digest Hebdomadaire Parc Automobile</h3>
            <p><strong>Semaine du %s</strong></p>
            
            <h4>🚨 Alertes</h4>
            <ul>
                <li>Véhicules critiques: <strong style="color: red;">%d</strong></li>
                <li>Véhicules en alerte: <strong style="color: orange;">%d</strong></li>
                <li>Documents expirant: <strong>%d</strong></li>
            </ul>
            
            <h4>🚗 Missions</h4>
            <ul>
                <li>En attente d'approbation: <strong>%d</strong></li>
                <li>Terminées cette semaine: <strong>%d</strong></li>
                <li>À venir (7 jours): <strong>%d</strong></li>
            </ul>
            """,
            today.strftime('%d/%m/%Y'),
            len(vehicles_critical),
            len(vehicles_warning),
            len(docs_expiring),
            len(missions_pending),
            len(missions_done),
            len(missions_upcoming),
        )
        
        # Envoyer notification interne à chaque fleet manager
        for manager in fleet_managers:
            try:
                # Notification interne via message_notify
                self.env['mail.thread'].message_notify(
                    partner_ids=manager.partner_id.ids,
                    body=notification_body,
                    subject=_("Digest Hebdomadaire Parc Auto - Semaine %s") % today.strftime('%W/%Y'),
                    model='fleet.vehicle',
                    res_id=False,
                )
                
                # Créer activité si missions en attente d'approbation
                if missions_pending:
                    # Trouver ou créer un véhicule pour attacher l'activité (utiliser le premier critique ou le premier de la liste)
                    ref_vehicle = vehicles_critical[:1] or vehicles_warning[:1] or self.search([], limit=1)
                    if ref_vehicle:
                        # Vérifier si activité similaire existe déjà
                        existing_activity = self.env['mail.activity'].search([
                            ('res_model', '=', 'fleet.mission'),
                            ('user_id', '=', manager.id),
                            ('summary', 'ilike', 'approbation'),
                            ('date_deadline', '>=', today),
                        ], limit=1)
                        
                        if not existing_activity:
                            for mission in missions_pending[:5]:  # Limit to 5 activities
                                mission.activity_schedule(
                                    'mail.mail_activity_data_todo',
                                    user_id=manager.id,
                                    summary=_("Mission en attente d'approbation: %s") % mission.name,
                                    note=_("Cette mission attend votre validation depuis le %s") % mission.date_request.strftime('%d/%m/%Y'),
                                    date_deadline=today + timedelta(days=2),
                                )
                
                _logger.info("Weekly digest sent to %s", manager.name)
                
            except Exception as e:
                _logger.error("Error sending weekly digest to %s: %s", manager.name, str(e))
                continue
        
        # Envoyer email aux responsables configurés
        template = self.env.ref('custom_fleet_management.mail_template_weekly_digest', raise_if_not_found=False)
        if template:
            for company in self.env['res.company'].search([]):
                try:
                    template.send_mail(company.id, force_send=False)
                    _logger.info("Weekly digest email sent for company %s", company.name)
                except Exception as e:
                    _logger.error("Error sending weekly digest email for company %s: %s", company.name, str(e))
        
        _logger.info("Weekly fleet digest completed")
    
    @api.constrains('date_prochaine_visite', 'date_fin_assurance')
    def _check_deadline_dates(self):
        """Validation métier des dates d'échéances."""
        today = date.today()
        for vehicle in self:
            if vehicle.date_prochaine_visite and vehicle.date_prochaine_visite < today - timedelta(days=365):
                raise ValidationError(_(
                    "La date de visite technique pour %s semble trop ancienne. "
                    "Veuillez vérifier la date saisie.", vehicle.name
                ))
            
            if vehicle.date_fin_assurance and vehicle.date_fin_assurance < today - timedelta(days=90):
                raise ValidationError(_(
                    "L'assurance du véhicule %s est expirée depuis plus de 90 jours. "
                    "Veuillez régulariser la situation avant de continuer.", vehicle.name
                ))
