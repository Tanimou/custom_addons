# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FleetVehicleDocument(models.Model):
    """
    Modèle pour gérer les documents administratifs des véhicules.
    
    Types de documents:
    - Carte grise (certificat d'immatriculation)
    - Assurance (police d'assurance)
    - Visite technique (contrôle technique)
    - Vignette (taxe circulation)
    - Permis de conduire
    - Contrôle pollution (test d'émissions)
    - Procès-verbal (PV, contraventions)
    - Carnet d'entretien
    - Autres documents administratifs
    
    Fonctionnalités:
    - Suivi des dates d'expiration
    - Alertes J-30
    - Archivage des pièces jointes
    - Calcul automatique du statut
    """
    _name = 'fleet.vehicle.document'
    _description = 'Document Véhicule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, create_date desc'
    _rec_names_search = ['vehicle_id', 'document_type', 'document_number']

    # ========== IDENTIFICATION ==========
    
    name = fields.Char(
        string='Libellé',
        compute='_compute_name',
        store=True,
        help="Libellé automatique du document"
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help="Véhicule auquel le document est rattaché"
    )
    
    document_type = fields.Selection(
        [
            ('carte_grise', 'Carte Grise'),
            ('assurance', 'Assurance'),
            ('visite_technique', 'Visite Technique'),
            ('vignette', 'Vignette'),
            ('permis', 'Permis de Conduire'),
            ('controle_pollution', 'Contrôle Pollution'),
            ('pv', 'Procès-Verbal (PV)'),
            ('maintenance', 'Carnet Entretien'),
            ('other', 'Autre'),
        ],
        string='Type de Document',
        required=True,
        default='other',
        tracking=True,
        help="Catégorie du document administratif"
    )
    
    document_number = fields.Char(
        string='Numéro de Document',
        help="Numéro ou référence du document (ex: numéro de police, n° PV)"
    )
    
    # ========== DATES ==========
    
    issue_date = fields.Date(
        string='Date Émission',
        help="Date de délivrance du document"
    )
    
    expiry_date = fields.Date(
        string='Date Expiration',
        tracking=True,
        help="Date d'expiration du document"
    )
    
    days_to_expire = fields.Integer(
        string='Jours avant Expiration',
        compute='_compute_days_to_expire',
        store=True,
        help="Nombre de jours restants avant expiration"
    )
    
    # ========== ÉTAT ==========
    
    state = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('valid', 'Valide'),
            ('expiring_soon', 'Expire Bientôt'),
            ('expired', 'Expiré'),
            ('cancelled', 'Annulé'),
        ],
        string='État',
        compute='_compute_state',
        store=True,
        tracking=True,
        help="État calculé automatiquement selon la date d'expiration"
    )
    
    alert_level = fields.Selection(
        [
            ('green', 'Vert (OK)'),
            ('orange', 'Orange (Attention)'),
            ('red', 'Rouge (Urgent)'),
        ],
        string='Niveau Alerte',
        compute='_compute_alert_level',
        store=True,
        help="Niveau d'urgence pour le renouvellement"
    )
    
    # ========== PIÈCE JOINTE ==========
    
    attachment_id = fields.Many2many(
        'ir.attachment',
        string='Fichier Attaché',
        ondelete='cascade',
        help="Scan ou PDF du document"
    )
    
    attachment_name = fields.Char(
        related='attachment_id.name',
        string='Nom Fichier',
        readonly=False
    )
    
    has_attachment = fields.Boolean(
        string='Fichier Disponible',
        compute='_compute_has_attachment',
        store=True,
        help="Indique si une pièce jointe existe"
    )
    
    # ========== RESPONSABLE ==========
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
        help="Utilisateur en charge du suivi du document"
    )
    
    # ========== MONTANTS (pour assurance, PV, etc.) ==========
    
    amount = fields.Float(
        string='Montant',
        help="Montant associé (prime assurance, montant PV, coût du document)"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    
    # ========== SOCIÉTÉ ==========
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        help="Société propriétaire du document"
    )
    
    # ========== NOTES ==========
    
    notes = fields.Html(
        string='Notes',
        help="Remarques sur le document"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        ('check_dates', 'CHECK(expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date)',
         "La date d'expiration doit être postérieure à la date d'émission!"),
    ]
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('vehicle_id', 'document_type', 'document_number')
    def _compute_name(self):
        """Génère le libellé automatique du document."""
        for doc in self:
            type_label = dict(doc._fields['document_type'].selection).get(doc.document_type, 'Document')
            vehicle_name = doc.vehicle_id.name if doc.vehicle_id else 'N/A'
            
            if doc.document_number:
                doc.name = f"{type_label} - {vehicle_name} - N°{doc.document_number}"
            else:
                doc.name = f"{type_label} - {vehicle_name}"
    
    @api.depends('expiry_date')
    def _compute_days_to_expire(self):
        """Calcule le nombre de jours avant expiration."""
        today = date.today()
        
        for doc in self:
            if doc.expiry_date:
                delta = doc.expiry_date - today
                doc.days_to_expire = delta.days
            else:
                doc.days_to_expire = 9999  # Pas d'expiration
    
    @api.depends('expiry_date', 'days_to_expire')
    def _compute_state(self):
        """
        Calcule l'état du document selon la date d'expiration.
        
        États:
        - draft: Aucun expiry_date défini
        - expired: Date passée
        - expiring_soon: Dans moins de 30 jours
        - valid: Plus de 30 jours
        """
        for doc in self:
            if not doc.expiry_date:
                doc.state = 'draft'
            elif doc.days_to_expire < 0:
                doc.state = 'expired'
            elif doc.days_to_expire <= 30:
                doc.state = 'expiring_soon'
            else:
                doc.state = 'valid'
    
    @api.depends('days_to_expire', 'state')
    def _compute_alert_level(self):
        """
        Détermine le niveau d'alerte pour la visualisation.
        
        Niveaux:
        - green: > 30 jours
        - orange: 0-30 jours
        - red: expiré (< 0 jours)
        """
        for doc in self:
            if doc.state == 'expired':
                doc.alert_level = 'red'
            elif doc.state == 'expiring_soon':
                doc.alert_level = 'orange'
            else:
                doc.alert_level = 'green'
    
    @api.depends('attachment_id')
    def _compute_has_attachment(self):
        """Indique si une pièce jointe existe."""
        for doc in self:
            doc.has_attachment = bool(doc.attachment_id)
    
    # ========== MÉTHODES CRUD ==========
    
    @api.model_create_multi
    def create(self, vals_list):
        """Logique à la création."""
        documents = super().create(vals_list)
        
        for doc in documents:
            doc.message_post(
                body=_("Document créé: %s", doc.name),
                subject=_("Création Document")
            )
            
            # Si expire dans moins de 30 jours, créer activité immédiatement
            if doc.state in ('expiring_soon', 'expired'):
                doc._schedule_renewal_activity()
        
        return documents
    
    def write(self, vals):
        """Logique lors de la modification."""
        # Détection changement de date d'expiration
        if 'expiry_date' in vals:
            for doc in self:
                old_date = doc.expiry_date
                new_date = vals['expiry_date']
                
                if old_date != new_date:
                    doc.message_post(
                        body=_("Date d'expiration modifiée: %s → %s", old_date or 'N/A', new_date or 'N/A'),
                        subject=_("Modification Date")
                    )
        
        result = super().write(vals)
        
        # Recalculer et créer activité si nécessaire
        for doc in self:
            if doc.state in ('expiring_soon', 'expired'):
                doc._schedule_renewal_activity()
        
        return result
    
    # ========== MÉTHODES MÉTIER ==========
    
    def _schedule_renewal_activity(self):
        """
        Crée une activité de renouvellement si le document expire bientôt.
        Évite les doublons.
        """
        self.ensure_one()
        
        # Vérifier qu'il n'existe pas déjà une activité ouverte
        existing = self.env['mail.activity'].search([
            ('res_model', '=', 'fleet.vehicle.document'),
            ('res_id', '=', self.id),
            ('user_id', '=', self.responsible_id.id),
            ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
        ], limit=1)
        
        if existing:
            return  # Activité déjà existante
        
        # Créer l'activité
        summary = _("Renouveler: %s", self.name)
        
        if self.state == 'expired':
            note = _("⚠️ URGENT: Ce document est EXPIRÉ depuis %s jours!", abs(self.days_to_expire))
        else:
            note = _("Ce document expire dans %s jours. Planifier le renouvellement.", self.days_to_expire)
        
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.responsible_id.id,
            date_deadline=self.expiry_date if self.expiry_date else date.today(),
            summary=summary,
            note=note,
        )
    
    def action_renew(self):
        """
        Wizard pour renouveler le document.
        Crée un nouveau document avec nouvelle date d'expiration.
        """
        self.ensure_one()
        
        # Créer nouveau document (copie)
        new_doc = self.copy({
            'issue_date': date.today(),
            'expiry_date': date.today() + timedelta(days=365),  # Par défaut 1 an
            'state': 'valid',
            'notes': _("<p>Renouvellement du document %s</p>", self.name),
        })
        
        # Archiver l'ancien
        self.write({
            'state': 'cancelled',
            'notes': self.notes + f"<p><i>Document renouvelé → {new_doc.name}</i></p>" if self.notes else f"<p><i>Document renouvelé → {new_doc.name}</i></p>"
        })
        
        self.message_post(
            body=_("Document renouvelé. Nouveau document: %s", new_doc.name),
            subject=_("Renouvellement")
        )
        
        # Ouvrir le nouveau document
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nouveau Document'),
            'res_model': 'fleet.vehicle.document',
            'res_id': new_doc.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_upload_attachment(self):
        """Ouvre le formulaire pour uploader une pièce jointe."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter Pièce Jointe'),
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'fleet.vehicle.document',
                'default_res_id': self.id,
                'default_name': f"{self.name}.pdf",
            },
        }
    
    def action_send_expiry_alerts(self):
        """
        Cron job: Envoi alertes échéances J-30 (tous les jours à 05:00).
        Recherche les documents qui expirent dans alert_offset_days et envoie des alertes.
        
        Envoie:
        - Messages dans le chatter du véhicule
        - Notifications internes aux fleet managers
        - Activités de suivi pour chaque document
        - Emails via template
        
        Idempotent: ne crée pas de doublons d'activités.
        """
        ConfigParam = self.env['ir.config_parameter'].sudo()
        
        # Récupérer le délai d'alerte (par défaut 30 jours)
        alert_offset_days = int(ConfigParam.get_param('fleet.alert_offset_days', '30'))
        alert_date = date.today() + timedelta(days=alert_offset_days)
        
        # Rechercher tous les documents expirant dans les alert_offset_days jours
        # État: valid, expiring_soon, ou expired
        docs_to_alert = self.search([
            ('expiry_date', '<=', alert_date),
            ('expiry_date', '>=', date.today()),
            ('state', 'in', ['valid', 'expiring_soon']),
        ])
        
        _logger.info(
            "Checking %d documents for expiry alerts (J-%d)",
            len(docs_to_alert),
            alert_offset_days
        )
        
        if not docs_to_alert:
            _logger.info("No documents expiring within %d days", alert_offset_days)
            return
        
        # Récupérer les fleet managers pour les notifications
        fleet_manager_group = self.env.ref('custom_fleet_management.group_fleet_manager', raise_if_not_found=False)
        fleet_managers = self.env['res.users']
        if fleet_manager_group:
            fleet_managers = self.env['res.users'].search([
                ('group_ids', 'in', fleet_manager_group.ids),
                ('active', '=', True),
            ])
        
        # Grouper par véhicule pour poster un seul message par véhicule
        vehicles_with_alerts = {}
        for doc in docs_to_alert:
            if doc.vehicle_id not in vehicles_with_alerts:
                vehicles_with_alerts[doc.vehicle_id] = []
            vehicles_with_alerts[doc.vehicle_id].append(doc)
        
        # Traiter chaque véhicule - poster un message simple dans le chatter
        alert_count = 0
        notification_count = 0
        activity_count = 0
        
        for vehicle, docs in vehicles_with_alerts.items():
            # Créer activités pour chaque document
            for doc in docs:
                doc._schedule_renewal_activity()
                activity_count += 1
            
            # Construire le message pour le chatter et notifications
            doc_list_text = []
            doc_list_html = []
            for doc in docs:
                days_left = (doc.expiry_date - date.today()).days
                urgency_emoji = "🔴" if days_left <= 7 else "🟠" if days_left <= 15 else "🟡"
                doc_list_text.append(f"• {doc.document_type}: expire le {doc.expiry_date.strftime('%d/%m/%Y')} ({days_left} jours)")
                doc_list_html.append(
                    f"<li>{urgency_emoji} <strong>{doc.document_type}</strong>: "
                    f"expire le {doc.expiry_date.strftime('%d/%m/%Y')} ({days_left} jours)</li>"
                )
            
            message_body = _(
                "⚠️ Alerte Échéance Administrative J-%d\n\n"
                "Documents concernés:\n%s\n\n"
                "Veuillez planifier le renouvellement de ces documents.",
                alert_offset_days,
                '\n'.join(doc_list_text)
            )
            
            # Message HTML pour notifications
            notification_body = _(
                """
                <h4>⚠️ Alerte Échéance Administrative J-%d</h4>
                <p><strong>Véhicule:</strong> %s</p>
                <p><strong>Documents concernés:</strong></p>
                <ul>%s</ul>
                <p><em>Veuillez planifier le renouvellement de ces documents.</em></p>
                """,
                alert_offset_days,
                vehicle.name,
                ''.join(doc_list_html)
            )
            
            try:
                # 1. Poster dans le chatter du véhicule
                vehicle.message_post(
                    body=message_body,
                    subject=_("Échéance Administrative J-%d: %s", alert_offset_days, vehicle.name),
                    message_type='notification',
                )
                alert_count += 1
                
                # 2. Envoyer notification interne aux fleet managers
                if fleet_managers:
                    for manager in fleet_managers:
                        try:
                            self.env['mail.thread'].message_notify(
                                partner_ids=manager.partner_id.ids,
                                body=notification_body,
                                subject=_("⚠️ Alerte Document: %s", vehicle.name),
                                model='fleet.vehicle',
                                res_id=vehicle.id,
                            )
                            notification_count += 1
                        except Exception as e:
                            _logger.warning(
                                "Failed to notify manager %s for vehicle %s: %s",
                                manager.name, vehicle.name, str(e)
                            )
                
                # 3. Créer activité pour le fleet manager si documents critiques (< 7 jours)
                critical_docs = [d for d in docs if (d.expiry_date - date.today()).days <= 7]
                if critical_docs and fleet_managers:
                    for manager in fleet_managers[:1]:  # Une activité par véhicule au premier manager
                        # Vérifier si activité similaire existe
                        existing = self.env['mail.activity'].search([
                            ('res_model', '=', 'fleet.vehicle'),
                            ('res_id', '=', vehicle.id),
                            ('user_id', '=', manager.id),
                            ('summary', 'ilike', 'critique'),
                            ('date_deadline', '>=', date.today()),
                        ], limit=1)
                        
                        if not existing:
                            vehicle.activity_schedule(
                                'mail.mail_activity_data_todo',
                                user_id=manager.id,
                                summary=_("🔴 Documents critiques à renouveler"),
                                note=_("Ce véhicule a %d document(s) expirant dans moins de 7 jours:\n%s") % (
                                    len(critical_docs),
                                    '\n'.join([f"- {d.document_type}" for d in critical_docs])
                                ),
                                date_deadline=date.today() + timedelta(days=3),
                            )
                
                _logger.info(
                    "Expiry alert posted for vehicle %s (%d documents)",
                    vehicle.name,
                    len(docs)
                )
            except Exception as e:
                _logger.error(
                    "Failed to post expiry alert for vehicle %s: %s",
                    vehicle.name,
                    str(e)
                )
        
        # 4. Envoyer email récapitulatif si template existe
        template = self.env.ref('custom_fleet_management.mail_template_document_deadline', raise_if_not_found=False)
        if template and fleet_managers:
            for manager in fleet_managers:
                if manager.email:
                    try:
                        # Envoyer pour chaque document en alerte
                        for doc in docs_to_alert[:10]:  # Limiter à 10 emails max
                            template.send_mail(doc.id, force_send=False)
                    except Exception as e:
                        _logger.warning("Failed to send email to %s: %s", manager.email, str(e))
        
        _logger.info(
            "Document expiry alerts completed: %d chatter posts, %d notifications, %d activities",
            alert_count, notification_count, activity_count
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Alertes Échéances'),
                'message': _('%d alertes envoyées, %d notifications, %d activités') % (
                    alert_count, notification_count, activity_count
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.constrains('expiry_date')
    def _check_expiry_date(self):
        """Validation métier de la date d'expiration."""
        for doc in self:
            if doc.expiry_date:
                # Alerter si expiration dans le passé de plus de 1 an (probablement une erreur de saisie)
                if (date.today() - doc.expiry_date).days > 365:
                    raise ValidationError(_(
                        "La date d'expiration (%s) semble anormalement ancienne (> 1 an dans le passé). "
                        "Veuillez vérifier la date saisie.",
                        doc.expiry_date
                    ))
                
                # Alerter si expiration dans plus de 10 ans (probablement une erreur)
                if (doc.expiry_date - date.today()).days > 3650:
                    raise ValidationError(_(
                        "La date d'expiration (%s) semble anormalement éloignée (> 10 ans). "
                        "Veuillez vérifier la date saisie.",
                        doc.expiry_date
                    ))
