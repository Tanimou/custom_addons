# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetPartnerContract(models.Model):
    """
    Modèle pour l'historique des contrats avec les partenaires du parc automobile.
    
    Phase 2 (TASK-006):
    - Historise tous les contrats (assurance, garage, remorqueur)
    - Stocke les dates, coûts et pièces jointes
    - Contrainte SQL anti-chevauchement pour assurances
    - Workflow: draft → active → expired/cancelled
    """
    _name = 'fleet.partner.contract'
    _description = 'Contrat Partenaire Fleet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _rec_name = 'contract_reference'

    # ========== IDENTIFICATION ==========
    
    contract_reference = fields.Char(
        string='Référence Contrat',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('Nouveau'),
        help="Référence unique du contrat (ex: CNT-0001)"
    )
    
    # ========== RELATIONS PRINCIPALES ==========
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Véhicule',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True,
        help="Véhicule concerné par ce contrat"
    )
    
    profile_id = fields.Many2one(
        'fleet.partner.profile',
        string='Partenaire',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help="Profil du partenaire (assureur, garage, remorqueur)"
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        related='profile_id.partner_id',
        store=True,
        readonly=True,
        help="Contact principal du partenaire"
    )
    
    partner_type = fields.Selection(
        related='profile_id.partner_type',
        store=True,
        readonly=True,
        string='Type de Partenaire',
        help="Type de partenaire (assureur, garage, remorqueur)"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Société propriétaire du contrat"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
        string='Devise'
    )
    
    # ========== TYPE & STATUT ==========
    
    contract_type = fields.Selection(
        [
            ('assurance', 'Assurance'),
            ('entretien', 'Entretien'),
            ('remorquage', 'Remorquage'),
            ('autre', 'Autre'),
        ],
        string='Type de Contrat',
        required=True,
        default='assurance',
        tracking=True,
        help="Nature du contrat avec le partenaire"
    )
    
    status = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('active', 'Actif'),
            ('expired', 'Expiré'),
            ('cancelled', 'Annulé'),
        ],
        string='Statut',
        default='draft',
        required=True,
        tracking=True,
        help="Statut du contrat"
    )
    
    # ========== DATES ==========
    
    date_start = fields.Date(
        string='Date Début',
        required=True,
        tracking=True,
        default=fields.Date.today,
        help="Date d'entrée en vigueur du contrat"
    )
    
    date_end = fields.Date(
        string='Date Fin',
        tracking=True,
        help="Date d'expiration du contrat"
    )
    
    duration_days = fields.Integer(
        string='Durée (jours)',
        compute='_compute_duration',
        store=True,
        help="Durée du contrat en jours"
    )
    
    days_remaining = fields.Integer(
        string='Jours Restants',
        compute='_compute_days_remaining',
        store=True,
        help="Nombre de jours avant expiration"
    )
    
    is_expiring_soon = fields.Boolean(
        string='Expire Bientôt',
        compute='_compute_expiring_status',
        store=True,
        help="Vrai si le contrat expire dans les 30 jours"
    )
    
    is_expired = fields.Boolean(
        string='Expiré',
        compute='_compute_expiring_status',
        store=True,
        help="Vrai si le contrat est expiré"
    )
    
    # ========== COÛTS ==========
    
    cost = fields.Monetary(
        string='Coût',
        currency_field='currency_id',
        tracking=True,
        help="Coût total du contrat"
    )
    
    cost_frequency = fields.Selection(
        [
            ('once', 'Unique'),
            ('monthly', 'Mensuel'),
            ('quarterly', 'Trimestriel'),
            ('yearly', 'Annuel'),
        ],
        string='Fréquence',
        default='yearly',
        help="Fréquence de paiement du contrat"
    )
    
    # ========== DÉTAILS ==========
    
    notes = fields.Html(
        string='Notes',
        help="Notes et conditions particulières du contrat"
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_contract_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Pièces Jointes',
        help="Documents liés au contrat (PDF, images)"
    )
    
    attachment_count = fields.Integer(
        string='Nombre de Pièces',
        compute='_compute_attachment_count',
        help="Nombre de documents attachés"
    )
    
    # ========== RELATIONS ADDITIONNELLES ==========
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
        help="Utilisateur responsable de ce contrat"
    )
    
    # ========== SQL CONSTRAINTS ==========
    
    _sql_constraints = [
        (
            'contract_reference_unique',
            'UNIQUE(contract_reference)',
            'La référence du contrat doit être unique!'
        ),
        (
            'dates_check',
            'CHECK(date_end IS NULL OR date_end >= date_start)',
            'La date de fin doit être postérieure à la date de début!'
        ),
        (
            'cost_positive',
            'CHECK(cost >= 0)',
            'Le coût doit être positif ou nul!'
        ),
    ]
    
    # ========== MÉTHODES COMPUTE ==========
    
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        """Calcule la durée du contrat en jours."""
        for contract in self:
            if contract.date_start and contract.date_end:
                contract.duration_days = (contract.date_end - contract.date_start).days
            else:
                contract.duration_days = 0
    
    @api.depends('date_end')
    def _compute_days_remaining(self):
        """Calcule le nombre de jours avant expiration."""
        today = date.today()
        for contract in self:
            if contract.date_end:
                contract.days_remaining = (contract.date_end - today).days
            else:
                contract.days_remaining = 0
    
    @api.depends('date_end', 'status')
    def _compute_expiring_status(self):
        """Détermine si le contrat expire bientôt ou est expiré."""
        today = date.today()
        warning_threshold = 30  # jours
        
        for contract in self:
            if not contract.date_end or contract.status in ('cancelled', 'draft'):
                contract.is_expiring_soon = False
                contract.is_expired = False
                continue
            
            days_diff = (contract.date_end - today).days
            
            contract.is_expired = days_diff < 0
            contract.is_expiring_soon = 0 <= days_diff <= warning_threshold
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Compte le nombre de pièces jointes."""
        for contract in self:
            contract.attachment_count = len(contract.attachment_ids)
    
    # ========== CONTRAINTES ==========
    
    @api.constrains('date_start', 'date_end')
    def _check_contract_dates(self):
        """Valide que la date de fin est postérieure à la date de début."""
        for contract in self:
            if contract.date_start and contract.date_end:
                if contract.date_end < contract.date_start:
                    raise ValidationError(_(
                        "La date de fin (%s) doit être postérieure à la date de début (%s) "
                        "pour le contrat %s.",
                        contract.date_end,
                        contract.date_start,
                        contract.contract_reference
                    ))
    
    @api.constrains('vehicle_id', 'profile_id', 'contract_type', 'date_start', 'date_end', 'status')
    def _check_no_overlapping_insurance(self):
        """
        Empêche le chevauchement des contrats d'assurance pour un même véhicule.
        Note: Seuls les contrats 'active' sont vérifiés.
        """
        for contract in self:
            # Ne vérifier que les contrats d'assurance actifs
            if contract.contract_type != 'assurance' or contract.status != 'active':
                continue
            
            if not contract.date_end:
                # Contrat sans date de fin = durée indéterminée
                # Vérifier qu'il n'y a pas d'autres contrats actifs
                overlapping = self.search([
                    ('id', '!=', contract.id),
                    ('vehicle_id', '=', contract.vehicle_id.id),
                    ('contract_type', '=', 'assurance'),
                    ('status', '=', 'active'),
                    ('date_start', '<=', contract.date_start),
                    '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', contract.date_start),
                ], limit=1)
                
                if overlapping:
                    raise ValidationError(_(
                        "Un contrat d'assurance actif existe déjà pour le véhicule %s "
                        "sur cette période. Contrat existant: %s",
                        contract.vehicle_id.name,
                        overlapping.contract_reference
                    ))
            else:
                # Contrat avec date de fin = période définie
                overlapping = self.search([
                    ('id', '!=', contract.id),
                    ('vehicle_id', '=', contract.vehicle_id.id),
                    ('contract_type', '=', 'assurance'),
                    ('status', '=', 'active'),
                    '|',
                    '&',
                    ('date_start', '<=', contract.date_start),
                    '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', contract.date_start),
                    '&',
                    ('date_start', '<=', contract.date_end),
                    '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', contract.date_start),
                ], limit=1)
                
                if overlapping:
                    raise ValidationError(_(
                        "Un contrat d'assurance actif chevauche la période du %s au %s "
                        "pour le véhicule %s. Contrat existant: %s",
                        contract.date_start,
                        contract.date_end,
                        contract.vehicle_id.name,
                        overlapping.contract_reference
                    ))
    
    # ========== MÉTHODES CRUD ==========
    
    @api.model_create_multi
    def create(self, vals_list):
        """Génère automatiquement la référence du contrat."""
        for vals in vals_list:
            if vals.get('contract_reference', _('Nouveau')) == _('Nouveau'):
                # Génère une référence unique
                sequence = self.env['ir.sequence'].next_by_code('fleet.partner.contract') or _('Nouveau')
                vals['contract_reference'] = sequence
        
        contracts = super().create(vals_list)
        
        # Log la création dans le chatter
        for contract in contracts:
            contract.message_post(
                body=_("Contrat créé: %s avec %s", 
                       contract.contract_type,
                       contract.partner_id.name),
                subject=_("Création Contrat")
            )
        
        return contracts
    
    def write(self, vals):
        """Log les changements importants dans le chatter."""
        # Log changement de statut
        if 'status' in vals:
            for contract in self:
                old_status = dict(self._fields['status'].selection).get(contract.status)
                new_status = dict(self._fields['status'].selection).get(vals['status'])
                
                if old_status != new_status:
                    contract.message_post(
                        body=_("Statut modifié: %s → %s", old_status, new_status),
                        subject=_("Changement Statut Contrat")
                    )
        
        # Log changement de dates
        if 'date_start' in vals or 'date_end' in vals:
            for contract in self:
                changes = []
                if 'date_start' in vals:
                    changes.append(f"Début: {vals['date_start']}")
                if 'date_end' in vals:
                    changes.append(f"Fin: {vals['date_end']}")
                
                if changes:
                    contract.message_post(
                        body=_("Dates du contrat mises à jour: %s", ', '.join(changes)),
                        subject=_("Modification Dates")
                    )
        
        return super().write(vals)
    
    # ========== MÉTHODES ACTION ==========
    
    def action_activate(self):
        """Active le contrat (draft → active)."""
        for contract in self:
            if contract.status == 'draft':
                contract.write({'status': 'active'})
                contract.message_post(
                    body=_("Contrat activé"),
                    subject=_("Activation Contrat")
                )
    
    def action_cancel(self):
        """Annule le contrat."""
        for contract in self:
            if contract.status in ('draft', 'active'):
                contract.write({'status': 'cancelled'})
                contract.message_post(
                    body=_("Contrat annulé"),
                    subject=_("Annulation Contrat")
                )
    
    def action_renew(self):
        """Crée un nouveau contrat en se basant sur celui-ci."""
        self.ensure_one()
        
        # Calcule les nouvelles dates
        new_start = self.date_end or date.today()
        duration_days = self.duration_days if self.duration_days > 0 else 365
        new_end = new_start + fields.Date.to_date(f"+{duration_days}d")
        
        # Copie le contrat avec nouvelles dates
        new_contract = self.copy({
            'date_start': new_start,
            'date_end': new_end,
            'status': 'draft',
        })
        
        self.message_post(
            body=_("Nouveau contrat créé: %s", new_contract.contract_reference),
            subject=_("Renouvellement Contrat")
        )
        
        return {
            'name': _('Renouvellement Contrat'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.partner.contract',
            'res_id': new_contract.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_vehicle(self):
        """Ouvre la fiche du véhicule."""
        self.ensure_one()
        return {
            'name': _('Véhicule'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle',
            'res_id': self.vehicle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_partner(self):
        """Ouvre la fiche du partenaire."""
        self.ensure_one()
        return {
            'name': _('Partenaire'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def cron_expire_contracts(self):
        """
        Cron job: Marque les contrats actifs comme expirés si la date de fin est dépassée.
        Exécuté quotidiennement.
        """
        today = date.today()
        expired_contracts = self.search([
            ('status', '=', 'active'),
            ('date_end', '<', today),
        ])
        
        for contract in expired_contracts:
            contract.write({'status': 'expired'})
            contract.message_post(
                body=_("Contrat expiré automatiquement"),
                subject=_("Expiration Contrat")
            )
        
        return len(expired_contracts)
