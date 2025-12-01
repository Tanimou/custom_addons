# -*- coding: utf-8 -*-
"""Fleet Incident Ticket model for managing breakdowns, towing and repairs.

This module implements TASK-009 from Phase 3 of the feature plan:
- Sequence PNR-####
- Fields: vehicle_id, driver_id, towing_partner_id, garage_partner_id
- Status workflow: draft → towing → repair → closed
- Links to fleet.maintenance.intervention
- Estimated and actual costs
"""

from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FleetIncidentTicket(models.Model):
    _name = "fleet.incident.ticket"
    _description = "Ticket d'incident véhicule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "reference"

    # =========================================================================
    # FIELDS - Identification
    # =========================================================================
    reference = fields.Char(
        string="Référence",
        copy=False,
        readonly=True,
        default="/",
        help="Numéro de ticket généré automatiquement (PNR-####)",
    )
    name = fields.Char(
        string="Titre",
        required=True,
        tracking=True,
        help="Description courte de l'incident",
    )
    active = fields.Boolean(default=True)

    # =========================================================================
    # FIELDS - Vehicle and Driver
    # =========================================================================
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Véhicule",
        required=True,
        tracking=True,
        index=True,
        ondelete="restrict",
        domain="[('company_id', 'in', [company_id, False])]",
        help="Véhicule concerné par l'incident",
    )
    driver_id = fields.Many2one(
        "res.partner",
        string="Conducteur",
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Conducteur au moment de l'incident",
    )
    license_plate = fields.Char(
        related="vehicle_id.license_plate",
        store=True,
        string="Immatriculation",
    )

    # =========================================================================
    # FIELDS - Company and Currency
    # =========================================================================
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # =========================================================================
    # FIELDS - Incident Details
    # =========================================================================
    incident_type = fields.Selection(
        selection=[
            ("breakdown", "Panne"),
            ("accident", "Accident"),
            ("theft", "Vol"),
            ("vandalism", "Vandalisme"),
            ("other", "Autre"),
        ],
        string="Type d'incident",
        required=True,
        default="breakdown",
        tracking=True,
    )
    incident_date = fields.Datetime(
        string="Date de l'incident",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    incident_location = fields.Char(
        string="Lieu de l'incident",
        tracking=True,
        help="Adresse ou description du lieu de l'incident",
    )
    description = fields.Html(
        string="Description détaillée",
        sanitize_style=True,
        help="Description complète de l'incident, circonstances, etc.",
    )
    priority = fields.Selection(
        selection=[
            ("0", "Normale"),
            ("1", "Haute"),
            ("2", "Urgente"),
            ("3", "Critique"),
        ],
        string="Priorité",
        default="0",
        tracking=True,
    )

    # =========================================================================
    # FIELDS - Partner Links
    # =========================================================================
    towing_partner_id = fields.Many2one(
        "fleet.partner.profile",
        string="Remorqueur",
        domain="[('partner_type', '=', 'remorqueur'), ('supplier_approved', '=', True), ('company_id', 'in', [company_id, False])]",
        tracking=True,
        help="Partenaire remorqueur assigné à l'incident",
    )
    towing_contact_id = fields.Many2one(
        "res.partner",
        related="towing_partner_id.partner_id",
        string="Contact remorqueur",
        store=True,
    )
    garage_partner_id = fields.Many2one(
        "fleet.partner.profile",
        string="Garage",
        domain="[('partner_type', '=', 'garage'), ('supplier_approved', '=', True), ('company_id', 'in', [company_id, False])]",
        tracking=True,
        help="Garage assigné pour les réparations",
    )
    garage_contact_id = fields.Many2one(
        "res.partner",
        related="garage_partner_id.partner_id",
        string="Contact garage",
        store=True,
    )
    insurance_partner_id = fields.Many2one(
        "fleet.partner.profile",
        string="Assureur",
        domain="[('partner_type', '=', 'assureur'), ('supplier_approved', '=', True), ('company_id', 'in', [company_id, False])]",
        tracking=True,
        help="Assureur notifié de l'incident",
    )

    # =========================================================================
    # FIELDS - Status Workflow
    # =========================================================================
    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("towing", "Remorquage"),
            ("repair", "Réparation"),
            ("closed", "Clôturé"),
            ("cancelled", "Annulé"),
        ],
        string="État",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
        group_expand="_group_expand_states",
    )

    # =========================================================================
    # FIELDS - Towing Details
    # =========================================================================
    towing_scheduled_date = fields.Datetime(
        string="Remorquage planifié",
        tracking=True,
    )
    towing_actual_date = fields.Datetime(
        string="Remorquage effectif",
        tracking=True,
    )
    towing_destination = fields.Char(
        string="Destination remorquage",
        help="Adresse de destination du remorquage (garage, dépôt, etc.)",
    )
    towing_notes = fields.Text(
        string="Notes remorquage",
    )
    towing_calendar_event_id = fields.Many2one(
        "calendar.event",
        string="Événement remorquage",
        copy=False,
    )

    # =========================================================================
    # FIELDS - Repair Details
    # =========================================================================
    repair_start_date = fields.Date(
        string="Début réparation",
        tracking=True,
    )
    repair_end_date = fields.Date(
        string="Fin réparation",
        tracking=True,
    )
    repair_notes = fields.Text(
        string="Notes réparation",
    )

    # =========================================================================
    # FIELDS - Maintenance Integration
    # =========================================================================
    intervention_id = fields.Many2one(
        "fleet.maintenance.intervention",
        string="Intervention maintenance",
        tracking=True,
        domain="[('vehicle_id', '=', vehicle_id)]",
        help="Intervention de maintenance curative liée à cet incident",
    )
    intervention_state = fields.Selection(
        related="intervention_id.state",
        string="État intervention",
        store=True,
    )

    # =========================================================================
    # FIELDS - Costs
    # =========================================================================
    estimated_towing_cost = fields.Monetary(
        string="Coût remorquage estimé",
        currency_field="currency_id",
    )
    actual_towing_cost = fields.Monetary(
        string="Coût remorquage réel",
        currency_field="currency_id",
        tracking=True,
    )
    estimated_repair_cost = fields.Monetary(
        string="Coût réparation estimé",
        currency_field="currency_id",
    )
    actual_repair_cost = fields.Monetary(
        string="Coût réparation réel",
        currency_field="currency_id",
        tracking=True,
    )
    total_estimated_cost = fields.Monetary(
        string="Coût total estimé",
        compute="_compute_total_costs",
        store=True,
        currency_field="currency_id",
    )
    total_actual_cost = fields.Monetary(
        string="Coût total réel",
        compute="_compute_total_costs",
        store=True,
        currency_field="currency_id",
    )

    # =========================================================================
    # FIELDS - Documents
    # =========================================================================
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "fleet_incident_attachment_rel",
        "incident_id",
        "attachment_id",
        string="Pièces jointes",
        help="Photos, constats, rapports, etc.",
    )
    attachment_count = fields.Integer(
        compute="_compute_attachment_count",
        string="Nombre de pièces jointes",
    )

    # =========================================================================
    # FIELDS - Responsible
    # =========================================================================
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
        help="Utilisateur responsable du suivi de l'incident",
    )
    close_date = fields.Datetime(
        string="Date de clôture",
        readonly=True,
        copy=False,
    )
    close_notes = fields.Text(
        string="Notes de clôture",
    )

    # =========================================================================
    # SQL CONSTRAINTS
    # =========================================================================
    _sql_constraints = [
        (
            "reference_unique",
            "UNIQUE(reference)",
            "La référence du ticket doit être unique.",
        ),
        (
            "repair_dates_check",
            "CHECK(repair_end_date IS NULL OR repair_start_date IS NULL OR repair_end_date >= repair_start_date)",
            "La date de fin de réparation doit être postérieure à la date de début.",
        ),
    ]

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    @api.depends("estimated_towing_cost", "estimated_repair_cost", "actual_towing_cost", "actual_repair_cost")
    def _compute_total_costs(self):
        for record in self:
            record.total_estimated_cost = record.estimated_towing_cost + record.estimated_repair_cost
            record.total_actual_cost = record.actual_towing_cost + record.actual_repair_cost

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    # =========================================================================
    # ONCHANGE METHODS
    # =========================================================================
    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        """Auto-fill driver and insurance from vehicle."""
        if self.vehicle_id:
            self.driver_id = self.vehicle_id.driver_id
            # Get insurance partner if available on vehicle
            if hasattr(self.vehicle_id, "insurance_partner_id") and self.vehicle_id.insurance_partner_id:
                self.insurance_partner_id = self.vehicle_id.insurance_partner_id
            # Suggest default tow partner from vehicle if available
            if hasattr(self.vehicle_id, "tow_partner_ids") and self.vehicle_id.tow_partner_ids:
                self.towing_partner_id = self.vehicle_id.tow_partner_ids[:1]
            # Suggest default garage from vehicle if available
            if hasattr(self.vehicle_id, "garage_partner_ids") and self.vehicle_id.garage_partner_ids:
                self.garage_partner_id = self.vehicle_id.garage_partner_ids[:1]

    @api.onchange("garage_partner_id")
    def _onchange_garage_partner_id(self):
        """Update towing destination when garage is selected."""
        if self.garage_partner_id and self.garage_partner_id.partner_id:
            partner = self.garage_partner_id.partner_id
            address_parts = [
                partner.street,
                partner.street2,
                partner.zip,
                partner.city,
            ]
            self.towing_destination = ", ".join(filter(None, address_parts))

    # =========================================================================
    # CRUD METHODS
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference") or vals.get("reference") == "/":
                vals["reference"] = self.env["ir.sequence"].next_by_code("fleet.incident.ticket") or "/"
        records = super().create(vals_list)
        # Post creation message
        for record in records:
            record.message_post(
                body=_("Ticket d'incident créé: %s") % record.name,
                message_type="notification",
            )
            # Notify responsible
            if record.responsible_id:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Nouveau ticket d'incident à traiter"),
                    note=_("Ticket %s: %s") % (record.reference, record.name),
                    user_id=record.responsible_id.id,
                )
        return records

    def write(self, vals):
        # Track state changes for chatter
        old_states = {r.id: r.state for r in self}
        old_interventions = {r.id: r.intervention_id for r in self}
        res = super().write(vals)
        if "state" in vals:
            for record in self:
                old_state = old_states.get(record.id)
                if old_state != vals["state"]:
                    state_labels = dict(self._fields["state"].selection)
                    record.message_post(
                        body=_("État changé de %s à %s") % (
                            state_labels.get(old_state, old_state),
                            state_labels.get(vals["state"], vals["state"]),
                        ),
                        message_type="notification",
                    )
            # Synchronize state to linked intervention (avoid infinite loop)
            if not self.env.context.get("_sync_from_intervention"):
                self._sync_state_to_intervention(vals["state"])
        # Sync back-reference when intervention_id is changed
        if "intervention_id" in vals:
            for record in self:
                old_intervention = old_interventions.get(record.id)
                # Clear back-reference on old intervention
                if old_intervention and old_intervention.incident_ticket_id == record:
                    old_intervention.write({"incident_ticket_id": False})
                # Set back-reference on new intervention
                if record.intervention_id:
                    record.intervention_id.write({"incident_ticket_id": record.id})
        return res

    def _sync_state_to_intervention(self, ticket_state):
        """Synchronize ticket state to linked maintenance intervention.
        
        State mapping:
        - repair → in_progress
        - closed → done
        - cancelled → cancelled
        """
        state_mapping = {
            "repair": "in_progress",
            "closed": "done",
            "cancelled": "cancelled",
        }
        intervention_state = state_mapping.get(ticket_state)
        if not intervention_state:
            return
        
        for record in self:
            if record.intervention_id:
                # Check if intervention state needs to be updated
                current_intervention_state = record.intervention_id.state
                if current_intervention_state != intervention_state:
                    # Use context flag to prevent infinite loop
                    record.intervention_id.with_context(
                        _sync_from_ticket=True
                    ).write({"state": intervention_state})

    # =========================================================================
    # GROUP EXPAND FOR KANBAN
    # =========================================================================
    @api.model
    def _group_expand_states(self, states, domain):
        """Return all states for kanban group expansion."""
        return [key for key, _ in self._fields["state"].selection]

    # =========================================================================
    # STATE WORKFLOW ACTIONS
    # =========================================================================
    def action_start_towing(self):
        """Move ticket to towing state."""
        for record in self:
            if record.state != "draft":
                raise UserError(_("Le ticket doit être en brouillon pour démarrer le remorquage."))
            if not record.towing_partner_id:
                raise UserError(_("Veuillez sélectionner un remorqueur avant de démarrer."))
            record.write({"state": "towing"})
            # Update vehicle state if field exists
            if hasattr(record.vehicle_id, "maintenance_state"):
                record.vehicle_id.write({"maintenance_state": "breakdown"})
            # Send notification
            template = self.env.ref(
                "custom_fleet_partner_network.mail_template_towing_scheduled",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(record.id, force_send=False)

    def action_start_repair(self):
        """Move ticket to repair state."""
        for record in self:
            if record.state != "towing":
                raise UserError(_("Le ticket doit être en remorquage pour démarrer la réparation."))
            if not record.garage_partner_id:
                raise UserError(_("Veuillez sélectionner un garage avant de démarrer la réparation."))
            record.write({
                "state": "repair",
                "repair_start_date": fields.Date.today(),
            })
            # Create intervention if not exists
            if not record.intervention_id:
                record.action_create_intervention()

    def action_close(self):
        """Close the incident ticket."""
        for record in self:
            if record.state not in ("towing", "repair"):
                raise UserError(_("Le ticket doit être en remorquage ou réparation pour être clôturé."))
            record.write({
                "state": "closed",
                "close_date": fields.Datetime.now(),
                "repair_end_date": record.repair_end_date or fields.Date.today(),
            })
            # Update vehicle state
            if hasattr(record.vehicle_id, "maintenance_state"):
                # Check if there are other open incidents for this vehicle
                other_open = self.search([
                    ("vehicle_id", "=", record.vehicle_id.id),
                    ("id", "!=", record.id),
                    ("state", "not in", ("closed", "cancelled")),
                ])
                if not other_open:
                    record.vehicle_id.write({"maintenance_state": "operational"})
            # Send completion notification
            template = self.env.ref(
                "custom_fleet_partner_network.mail_template_repair_completed",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(record.id, force_send=False)
            # Log in vehicle chatter
            if record.vehicle_id:
                record.vehicle_id.message_post(
                    body=_("Incident %s clôturé. Coût total: %s %s") % (
                        record.reference,
                        record.total_actual_cost,
                        record.currency_id.symbol or "",
                    ),
                    message_type="notification",
                )

    def action_cancel(self):
        """Cancel the incident ticket."""
        for record in self:
            if record.state == "closed":
                raise UserError(_("Un ticket clôturé ne peut pas être annulé."))
            record.write({"state": "cancelled"})
            # Update vehicle state if needed
            if hasattr(record.vehicle_id, "maintenance_state"):
                other_open = self.search([
                    ("vehicle_id", "=", record.vehicle_id.id),
                    ("id", "!=", record.id),
                    ("state", "not in", ("closed", "cancelled")),
                ])
                if not other_open:
                    record.vehicle_id.write({"maintenance_state": "operational"})

    def action_reset_to_draft(self):
        """Reset cancelled ticket to draft."""
        for record in self:
            if record.state != "cancelled":
                raise UserError(_("Seul un ticket annulé peut être remis en brouillon."))
            record.write({"state": "draft"})

    # =========================================================================
    # INTEGRATION ACTIONS
    # =========================================================================
    def action_create_intervention(self):
        """Create a curative maintenance intervention linked to this incident."""
        self.ensure_one()
        if self.intervention_id:
            raise UserError(_("Une intervention est déjà liée à ce ticket."))
        
        # Check if maintenance module is available
        if "fleet.maintenance.intervention" not in self.env:
            raise UserError(_("Le module de maintenance n'est pas installé."))
        
        intervention_vals = {
            "intervention_type": "curative",
            "vehicle_id": self.vehicle_id.id,
            "driver_id": self.driver_id.id if self.driver_id else False,
            "origin": self.reference,
            "description": self.description,
            "vendor_id": self.garage_contact_id.id if self.garage_contact_id else False,
            "company_id": self.company_id.id,
            "state": "submitted",
            "incident_ticket_id": self.id,  # Set back-reference to this ticket
        }
        
        # Add failure_type if breakdown
        if self.incident_type == "breakdown":
            intervention_vals["failure_type"] = "autre"
        
        intervention = self.env["fleet.maintenance.intervention"].create(intervention_vals)
        self.intervention_id = intervention
        
        self.message_post(
            body=_("Intervention de maintenance %s créée") % intervention.name,
            message_type="notification",
        )
        
        # Return action to view the intervention
        action = self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_action").sudo().read()[0]
        action["res_id"] = intervention.id
        action["views"] = [(self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_view_form").id, "form")]
        return action

    def action_view_intervention(self):
        """View the linked maintenance intervention."""
        self.ensure_one()
        if not self.intervention_id:
            raise UserError(_("Aucune intervention liée à ce ticket."))
        action = self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_action").sudo().read()[0]
        action["res_id"] = self.intervention_id.id
        action["views"] = [(self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_view_form").id, "form")]
        return action

    def action_schedule_towing(self):
        """Schedule a towing event in the calendar."""
        self.ensure_one()
        if not self.towing_scheduled_date:
            raise UserError(_("Veuillez définir la date de remorquage planifiée."))
        
        if self.towing_calendar_event_id:
            # Update existing event
            self.towing_calendar_event_id.write({
                "start": self.towing_scheduled_date,
                "stop": self.towing_scheduled_date + timedelta(hours=2),
            })
        else:
            # Create new event
            partners = []
            if self.responsible_id:
                partners.append(self.responsible_id.partner_id.id)
            if self.towing_contact_id:
                partners.append(self.towing_contact_id.id)
            if self.driver_id:
                partners.append(self.driver_id.id)
            
            event = self.env["calendar.event"].create({
                "name": _("Remorquage: %s") % self.reference,
                "start": self.towing_scheduled_date,
                "stop": self.towing_scheduled_date + timedelta(hours=2),
                "allday": False,
                "description": _("Remorquage du véhicule %s\nLieu: %s\nDestination: %s") % (
                    self.vehicle_id.display_name,
                    self.incident_location or "Non spécifié",
                    self.towing_destination or "Non spécifié",
                ),
                "partner_ids": [(6, 0, partners)],
            })
            self.towing_calendar_event_id = event
        
        self.message_post(
            body=_("Remorquage planifié le %s") % self.towing_scheduled_date,
            message_type="notification",
        )
        
        return {
            "type": "ir.actions.act_window",
            "res_model": "calendar.event",
            "res_id": self.towing_calendar_event_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # =========================================================================
    # CRON METHODS
    # =========================================================================
    @api.model
    def cron_send_incident_alerts(self):
        """Send daily alerts for pending incidents.
        
        This cron runs daily to alert about:
        - Open incidents not progressing
        - Towing scheduled within alert offset days
        """
        config = self.env["ir.config_parameter"].sudo()
        offset = int(config.get_param("custom_fleet_partner_network.fleet_partner_alert_offset", 30))
        
        # Find incidents with towing scheduled soon
        today = fields.Datetime.now()
        limit_date = today + timedelta(days=offset)
        
        # Pending drafts older than 24h
        draft_incidents = self.search([
            ("state", "=", "draft"),
            ("create_date", "<", today - timedelta(days=1)),
        ])
        
        # Towing scheduled within offset days
        towing_soon = self.search([
            ("state", "in", ("draft", "towing")),
            ("towing_scheduled_date", ">=", today),
            ("towing_scheduled_date", "<=", limit_date),
        ])
        
        template = self.env.ref(
            "custom_fleet_partner_network.mail_template_incident_alert",
            raise_if_not_found=False,
        )
        
        for incident in (draft_incidents | towing_soon):
            if template:
                template.send_mail(incident.id, force_send=False)
            # Create activity for responsible
            if incident.responsible_id:
                existing = incident.activity_ids.filtered(
                    lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")
                    and a.user_id == incident.responsible_id
                    and a.state == "planned"
                )
                if not existing:
                    incident.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Incident en attente"),
                        note=_("L'incident %s nécessite votre attention.") % incident.reference,
                        user_id=incident.responsible_id.id,
                    )

    @api.model
    def cron_send_incident_digest(self):
        """Send weekly digest of open incidents.
        
        Groups incidents by responsible and sends summary email.
        """
        config = self.env["ir.config_parameter"].sudo()
        digest_enabled = config.get_param(
            "custom_fleet_partner_network.fleet_partner_enable_weekly_digest", "True"
        )
        
        if str(digest_enabled).lower() in ("false", "0"):
            return
        
        # Get all open incidents
        open_incidents = self.search([
            ("state", "in", ("draft", "towing", "repair")),
            ("company_id", "=", self.env.company.id),
        ])
        
        if not open_incidents:
            return
        
        template = self.env.ref(
            "custom_fleet_partner_network.mail_template_incident_digest",
            raise_if_not_found=False,
        )
        
        if not template:
            return
        
        # Group by responsible and send digest
        responsibles = open_incidents.mapped("responsible_id")
        for responsible in responsibles:
            responsible_incidents = open_incidents.filtered(
                lambda r: r.responsible_id == responsible
            )
            if responsible_incidents:
                template.with_context(
                    incidents=responsible_incidents
                ).send_mail(responsible_incidents[0].id, force_send=False)
