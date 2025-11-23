# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class FleetMission(models.Model):
    """
    Modèle pour gérer les missions/déplacements des véhicules.
    
    Workflow: Brouillon → Soumis → Approuvé → Affecté → En cours → Terminé / Annulé
    
    Fonctionnalités:
    - Planification avec détection de conflits
    - Validation hiérarchique
    - Synchronisation calendrier (optionnel)
    - Génération ordre de mission PDF
    - Suivi kilométrique et consommation
    """
    _name = 'fleet.mission'
    _description = 'Mission Véhicule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _rec_names_search = ['name', 'route', 'vehicle_id.license_plate']

    # ========== IDENTIFICATION ==========
    
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('Nouveau'),
        help="Référence unique de la mission (ex: MIS-0001)"
    )
    
    order_number = fields.Char(
        string='N° Ordre de Mission',
        copy=False,
        readonly=True,
        help="Numéro de l'ordre de mission imprimable (ex: OMI-0001)"
    )
    
    # ========== DEMANDEUR & DATES ==========
    
    requester_id = fields.Many2one(
        'res.users',
        string='Demandeur',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help="Utilisateur qui a créé la demande de mission"
    )
    
    date_request = fields.Date(
        string='Date Demande',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Date de création de la demande"
    )
    
    date_start = fields.Datetime(
        string='Début Mission',
        required=True,
        tracking=True,
        help="Date et heure de début planifiées"
    )
    
    date_end = fields.Datetime(
        string='Fin Mission',
        required=True,
        tracking=True,
        help="Date et heure de fin planifiées"
    )
    
    duration_days = fields.Float(
        string='Durée (jours)',
        compute='_compute_duration',
        store=True,
        help="Durée calculée de la mission en jours"
    )
    
    # ========== VÉHICULE & CONDUCTEUR ==========
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        tracking=True,
        domain="[('active', '=', True), ('is_available', '=', True)]",
        help="Véhicule affecté à cette mission"
    )
    
    driver_id = fields.Many2one(
        'hr.employee',
        string='Conducteur',
        required=True,
        tracking=True,
        domain="[('active', '=', True)]",
        help="Conducteur assigné à la mission"
    )
    
    driver_partner_id = fields.Many2one(
        'res.partner',
        string='Conducteur (Partner)',
        related='driver_id.work_contact_id',
        store=True,
        help="Lien vers le partner pour compatibilité fleet"
    )
    
    # ========== TYPE & DÉTAILS MISSION ==========
    
    mission_type = fields.Selection(
        [
            ('urban', 'Course Urbaine'),
            ('intercity', 'Mission Interurbaine'),
            ('delivery', 'Livraison'),
            ('maintenance', 'Déplacement Maintenance'),
            ('administrative', 'Mission Administrative'),
            ('other', 'Autre'),
        ],
        string='Type de Mission',
        required=True,
        default='urban',
        tracking=True,
        help="Nature de la mission"
    )
    
    route = fields.Text(
        string='Itinéraire',
        required=True,
        help="Description du parcours (départ, étapes, destination)"
    )
    
    destination = fields.Char(
        string='Destination Principale',
        help="Lieu de destination principal"
    )
    
    objective = fields.Text(
        string='Objectif',
        help="But et description détaillée de la mission"
    )
    
    passengers = fields.Char(
        string='Passagers',
        help="Liste des passagers (si applicable)"
    )
    
    payload_description = fields.Char(
        string='Chargement',
        help="Description du chargement transporté"
    )
    
    # ========== KILOMÉTRAGE ==========
    
    odo_start = fields.Float(
        string='Kilométrage Départ',
        help="Relevé compteur au départ"
    )
    
    odo_end = fields.Float(
        string='Kilométrage Retour',
        help="Relevé compteur au retour"
    )
    
    distance_km = fields.Float(
        string='Distance (km)',
        compute='_compute_distance',
        store=True,
        help="Distance parcourue calculée"
    )
    
    estimated_consumption = fields.Float(
        string='Consommation Estimée (L)',
        compute='_compute_estimated_consumption',
        help="Consommation carburant estimée"
    )
    
    # ========== WORKFLOW & ÉTAT ==========
    
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('submitted', 'Soumis'),
            ('approved', 'Approuvé'),
            ('assigned', 'Affecté'),
            ('in_progress', 'En Cours'),
            ('done', 'Terminé'),
            ('cancelled', 'Annulé'),
        ],
        string='État',
        required=True,
        default='draft',
        tracking=True,
        help="État actuel de la mission dans le workflow"
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approuvé par',
        readonly=True,
        tracking=True,
        help="Manager qui a validé la mission"
    )
    
    approval_date = fields.Datetime(
        string='Date Approbation',
        readonly=True,
        help="Date et heure de validation"
    )
    
    cancellation_reason = fields.Text(
        string='Motif Annulation',
        help="Raison de l'annulation de la mission"
    )
    
    # ========== INTÉGRATION CALENDRIER ==========
    
    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Événement Calendrier',
        readonly=True,
        help="Événement créé dans le calendrier Odoo"
    )
    
    create_calendar_event = fields.Boolean(
        string='Créer Événement',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'fleet.create_calendar_events', default=False
        ),
        help="Créer automatiquement un événement dans le calendrier"
    )
    
    # ========== CONFLITS & ALERTES ==========
    
    has_conflict = fields.Boolean(
        string='Conflit Détecté',
        compute='_compute_has_conflict',
        help="Indique si la mission entre en conflit avec d'autres missions"
    )
    
    conflict_details = fields.Text(
        string='Détails Conflits',
        compute='_compute_has_conflict',
        help="Description des conflits détectés"
    )
    
    # ========== SOCIÉTÉ ==========
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        help="Société propriétaire de la mission"
    )
    
    # ========== NOTES ==========
    
    notes = fields.Html(
        string='Notes',
        help="Remarques et informations complémentaires"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        ('check_dates', 'CHECK(date_end >= date_start)',
         'La date de fin doit être postérieure à la date de début!'),
        ('check_odo', 'CHECK(odo_end IS NULL OR odo_start IS NULL OR odo_end >= odo_start)',
         'Le kilométrage de retour doit être supérieur au kilométrage de départ!'),
    ]
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        """Calcule la durée de la mission en jours."""
        for mission in self:
            if mission.date_start and mission.date_end:
                delta = mission.date_end - mission.date_start
                mission.duration_days = delta.total_seconds() / 86400.0
            else:
                mission.duration_days = 0.0
    
    @api.depends('odo_start', 'odo_end')
    def _compute_distance(self):
        """Calcule la distance parcourue."""
        for mission in self:
            if mission.odo_start and mission.odo_end:
                mission.distance_km = mission.odo_end - mission.odo_start
            else:
                mission.distance_km = 0.0
    
    @api.depends('distance_km', 'vehicle_id.fuel_type')
    def _compute_estimated_consumption(self):
        """
        Estime la consommation carburant.
        Utilise une valeur moyenne selon le type de véhicule.
        """
        # Consommations moyennes (L/100km) par type de carburant
        consumption_rates = {
            'gasoline': 8.0,
            'diesel': 6.5,
            'lpg': 9.0,
            'electric': 0.0,  # kWh, non géré ici
            'hybrid': 5.0,
        }
        
        for mission in self:
            if mission.distance_km and mission.vehicle_id.fuel_type:
                rate = consumption_rates.get(mission.vehicle_id.fuel_type, 7.0)
                mission.estimated_consumption = (mission.distance_km * rate) / 100.0
            else:
                mission.estimated_consumption = 0.0
    
    @api.depends('vehicle_id', 'driver_id', 'date_start', 'date_end', 'state')
    def _compute_has_conflict(self):
        """
        Détecte les conflits d'affectation.
        Un conflit existe si:
        - Le véhicule est déjà affecté sur une période qui chevauche
        - Le conducteur a déjà une mission sur une période qui chevauche
        """
        for mission in self:
            if mission.state in ('cancelled', 'done') or not mission.vehicle_id or not mission.date_start or not mission.date_end:
                mission.has_conflict = False
                mission.conflict_details = False
                continue
            
            conflicts = []
            
            # Cherche missions qui se chevauchent (même véhicule ou même conducteur)
            overlapping_domain = [
                ('id', '!=', mission.id),
                ('state', 'in', ['submitted', 'approved', 'assigned', 'in_progress']),
                ('date_start', '<', mission.date_end),
                ('date_end', '>', mission.date_start),
                '|',
                ('vehicle_id', '=', mission.vehicle_id.id),
                ('driver_id', '=', mission.driver_id.id),
            ]
            
            overlapping = self.search(overlapping_domain)
            
            for overlap in overlapping:
                if overlap.vehicle_id == mission.vehicle_id:
                    conflicts.append(f"⚠ Véhicule {mission.vehicle_id.name} déjà affecté à la mission {overlap.name} du {overlap.date_start.strftime('%d/%m/%Y %H:%M')} au {overlap.date_end.strftime('%d/%m/%Y %H:%M')}")
                if overlap.driver_id == mission.driver_id:
                    conflicts.append(f"⚠ Conducteur {mission.driver_id.name} déjà affecté à la mission {overlap.name} du {overlap.date_start.strftime('%d/%m/%Y %H:%M')} au {overlap.date_end.strftime('%d/%m/%Y %H:%M')}")
            
            mission.has_conflict = bool(conflicts)
            mission.conflict_details = '\n'.join(conflicts) if conflicts else False
    
    # ========== MÉTHODES CRUD ==========
    
    @api.model_create_multi
    def create(self, vals_list):
        """Génère la référence de mission lors de la création."""
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.mission') or _('Nouveau')
        
        missions = super().create(vals_list)
        
        for mission in missions:
            mission.message_post(
                body=_("Mission créée par %s", mission.requester_id.name),
                subject=_("Création Mission")
            )
        
        return missions
    
    def write(self, vals):
        """Logique lors de la modification."""
        # Si changement de dates, recalculer les conflits
        if any(key in vals for key in ['date_start', 'date_end', 'vehicle_id', 'driver_id']):
            self._compute_has_conflict()
        
        return super().write(vals)
    
    # ========== ACTIONS WORKFLOW ==========
    
    def action_submit(self):
        """
        Soumet la mission pour approbation.
        Transitions: draft → submitted
        """
        for mission in self:
            if mission.state != 'draft':
                raise UserError(_("Seules les missions en brouillon peuvent être soumises."))
            
            # Vérification des champs requis
            if not mission.route or not mission.objective:
                raise UserError(_("L'itinéraire et l'objectif sont obligatoires avant soumission."))
            
            # Alerte si conflit (mais n'empêche pas)
            if mission.has_conflict:
                mission.message_post(
                    body=f"⚠️ ATTENTION: Conflits détectés lors de la soumission:\n{mission.conflict_details}",
                    subject=_("Alerte Conflits"),
                    message_type='notification'
                )
            
            mission.write({'state': 'submitted'})
            
            # Créer une activité pour le Fleet Manager
            fleet_manager_group = self.env.ref('custom_fleet_management.group_fleet_manager')
            managers = self.env['res.users'].search([('group_ids', 'in', fleet_manager_group.ids)])
            
            for manager in managers:
                mission.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=manager.id,
                    summary=_("Approuver la mission %s", mission.name),
                    note=_("Nouvelle mission soumise par %s pour validation.", mission.requester_id.name),
                )
            
            mission.message_post(
                body=_("Mission soumise pour approbation."),
                subject=_("Soumission")
            )
    
    def action_approve(self):
        """
        Approuve la mission.
        Transitions: submitted → approved
        Nécessite droits Fleet Manager.
        """
        self.check_access_rights('write')
        self.check_access_rule('write')
        
        for mission in self:
            if mission.state != 'submitted':
                raise UserError(_("Seules les missions soumises peuvent être approuvées."))
            
            # Bloque si conflits critiques (configurable)
            block_on_conflict = self.env['ir.config_parameter'].sudo().get_param(
                'fleet.block_conflicting_missions', default='False'
            ) == 'True'
            
            if block_on_conflict and mission.has_conflict:
                raise UserError(_(
                    "Impossible d'approuver: conflits d'affectation détectés.\n\n%s",
                    mission.conflict_details
                ))
            
            mission.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            
            # Générer le numéro d'ordre de mission
            if not mission.order_number:
                mission.order_number = self.env['ir.sequence'].next_by_code('fleet.mission.order')
            
            # Notification au demandeur
            mission.message_post_with_source(
                'custom_fleet_management.mail_template_mission_approved',
                subtype_xmlid='mail.mt_comment',
            )
            
            mission.message_post(
                body=_("Mission approuvée par %s", self.env.user.name),
                subject=_("Approbation")
            )
    
    def action_assign(self):
        """
        Assigne définitivement le véhicule et le conducteur.
        Transitions: approved → assigned
        Synchronise avec le calendrier si activé.
        """
        for mission in self:
            if mission.state != 'approved':
                raise UserError(_("Seules les missions approuvées peuvent être assignées."))
            
            mission.write({'state': 'assigned'})
            
            # Création événement calendrier si activé
            if mission.create_calendar_event and not mission.calendar_event_id:
                mission._create_calendar_event()
            
            # Notification au conducteur
            if mission.driver_id.user_id:
                mission.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=mission.driver_id.user_id.id,
                    date_deadline=mission.date_start.date(),
                    summary=_("Mission assignée: %s", mission.name),
                    note=_("Vous êtes assigné à cette mission avec le véhicule %s.", mission.vehicle_id.name),
                )
            
            mission.message_post(
                body=_("Mission assignée. Véhicule: %s, Conducteur: %s", 
                       mission.vehicle_id.name, mission.driver_id.name),
                subject=_("Affectation")
            )
    
    def action_start(self):
        """
        Démarre la mission.
        Transitions: assigned → in_progress
        """
        for mission in self:
            if mission.state != 'assigned':
                raise UserError(_("Seules les missions assignées peuvent être démarrées."))
            
            if not mission.odo_start:
                raise UserError(_("Le kilométrage de départ doit être renseigné avant de démarrer."))
            
            mission.write({'state': 'in_progress'})
            
            mission.message_post(
                body=_("Mission démarrée. Kilométrage départ: %s km", mission.odo_start),
                subject=_("Démarrage")
            )
    
    def action_done(self):
        """
        Termine la mission.
        Transitions: in_progress → done
        """
        for mission in self:
            if mission.state != 'in_progress':
                raise UserError(_("Seules les missions en cours peuvent être terminées."))
            
            if not mission.odo_end:
                raise UserError(_("Le kilométrage de retour doit être renseigné avant de terminer."))
            
            if mission.odo_end < mission.odo_start:
                raise ValidationError(_("Le kilométrage de retour doit être supérieur au kilométrage de départ."))
            
            mission.write({'state': 'done'})
            
            # Mise à jour de l'odomètre du véhicule
            mission.vehicle_id.write({'odometer': mission.odo_end})
            
            mission.message_post(
                body=_("Mission terminée. Distance parcourue: %.2f km", mission.distance_km),
                subject=_("Clôture Mission")
            )
    
    def action_cancel(self):
        """
        Annule la mission.
        Possible depuis n'importe quel état sauf done.
        """
        for mission in self:
            if mission.state == 'done':
                raise UserError(_("Impossible d'annuler une mission terminée."))
            
            if not mission.cancellation_reason:
                raise UserError(_("Veuillez indiquer le motif d'annulation."))
            
            old_state = mission.state
            mission.write({'state': 'cancelled'})
            
            # Supprimer l'événement calendrier si existant
            if mission.calendar_event_id:
                mission.calendar_event_id.unlink()
            
            mission.message_post(
                body=_("Mission annulée (état précédent: %s). Motif: %s", 
                       dict(mission._fields['state'].selection)[old_state], 
                       mission.cancellation_reason),
                subject=_("Annulation")
            )
    
    def action_reset_to_draft(self):
        """Remet en brouillon (seulement depuis cancelled ou submitted)."""
        for mission in self:
            if mission.state not in ('cancelled', 'submitted'):
                raise UserError(_("Seules les missions annulées ou soumises peuvent être remises en brouillon."))
            
            mission.write({
                'state': 'draft',
                'approved_by': False,
                'approval_date': False,
                'cancellation_reason': False,
            })
            
            mission.message_post(
                body=_("Mission remise en brouillon."),
                subject=_("Réinitialisation")
            )
    
    # ========== MÉTHODES CALENDRIER ==========
    
    def _create_calendar_event(self):
        """Crée un événement dans le calendrier Odoo."""
        self.ensure_one()
        
        if self.calendar_event_id:
            return  # Déjà créé
        
        event = self.env['calendar.event'].create({
            'name': f"Mission {self.name} - {self.vehicle_id.name}",
            'start': self.date_start,
            'stop': self.date_end,
            'description': f"Mission: {self.objective}\nItinéraire: {self.route}\nVéhicule: {self.vehicle_id.name}\nConducteur: {self.driver_id.name}",
            'partner_ids': [(4, self.driver_partner_id.id)] if self.driver_partner_id else [],
            'user_id': self.driver_id.user_id.id if self.driver_id.user_id else self.env.user.id,
        })
        
        self.calendar_event_id = event.id
    
    def _update_calendar_event(self):
        """Met à jour l'événement calendrier si existant."""
        self.ensure_one()
        
        if not self.calendar_event_id:
            return
        
        self.calendar_event_id.write({
            'name': f"Mission {self.name} - {self.vehicle_id.name}",
            'start': self.date_start,
            'stop': self.date_end,
            'description': f"Mission: {self.objective}\nItinéraire: {self.route}\nVéhicule: {self.vehicle_id.name}\nConducteur: {self.driver_id.name}",
        })
    
    # ========== ACTIONS VUE ==========
    
    def action_print_mission_order(self):
        """Génère et imprime l'ordre de mission PDF."""
        self.ensure_one()
        return self.env.ref('custom_fleet_management.action_report_mission_order').report_action(self)
    
    @api.constrains('date_start', 'date_end')
    def _check_mission_dates(self):
        """Validation métier des dates."""
        for mission in self:
            if mission.date_start and mission.date_end:
                if mission.date_start >= mission.date_end:
                    raise ValidationError(_("La date de fin doit être postérieure à la date de début."))
                
                # Alerte si mission trop longue (> 30 jours)
                if (mission.date_end - mission.date_start).days > 30:
                    raise ValidationError(_(
                        "La durée de la mission (%s jours) semble anormalement longue. "
                        "Veuillez vérifier les dates ou créer plusieurs missions distinctes.",
                        int((mission.date_end - mission.date_start).days)
                    ))
