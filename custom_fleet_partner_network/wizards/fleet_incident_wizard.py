# -*- coding: utf-8 -*-
"""Fleet Incident Declaration Wizard.

This wizard provides a streamlined interface to quickly declare
a new incident from a vehicle form or from the fleet menu.
It collects essential information and creates a fleet.incident.ticket.

Part of TASK-010 from Phase 3.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FleetIncidentWizard(models.TransientModel):
    _name = "fleet.incident.wizard"
    _description = "Assistant de déclaration d'incident"

    # =========================================================================
    # FIELDS - Vehicle Selection
    # =========================================================================
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Véhicule",
        required=True,
        default=lambda self: self._default_vehicle_id(),
        domain="[('company_id', 'in', [company_id, False])]",
        help="Véhicule concerné par l'incident",
    )
    driver_id = fields.Many2one(
        "res.partner",
        string="Conducteur",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Conducteur au moment de l'incident (auto-rempli depuis le véhicule)",
    )
    license_plate = fields.Char(
        related="vehicle_id.license_plate",
        string="Immatriculation",
    )

    # =========================================================================
    # FIELDS - Company
    # =========================================================================
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )

    # =========================================================================
    # FIELDS - Incident Details
    # =========================================================================
    name = fields.Char(
        string="Titre",
        required=True,
        help="Description courte de l'incident",
    )
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
    )
    incident_date = fields.Datetime(
        string="Date de l'incident",
        required=True,
        default=fields.Datetime.now,
    )
    incident_location = fields.Char(
        string="Lieu de l'incident",
        help="Adresse ou description du lieu de l'incident",
    )
    description = fields.Html(
        string="Description détaillée",
        sanitize_style=True,
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
    )

    # =========================================================================
    # FIELDS - Partner Selection (Optional quick assignment)
    # =========================================================================
    towing_partner_id = fields.Many2one(
        "fleet.partner.profile",
        string="Remorqueur",
        domain="[('partner_type', '=', 'remorqueur'), ('company_id', 'in', [company_id, False])]",
        help="Sélectionner un remorqueur si connu",
    )
    garage_partner_id = fields.Many2one(
        "fleet.partner.profile",
        string="Garage",
        domain="[('partner_type', '=', 'garage'), ('company_id', 'in', [company_id, False])]",
        help="Sélectionner un garage si connu",
    )

    # =========================================================================
    # FIELDS - Workflow Options
    # =========================================================================
    start_towing = fields.Boolean(
        string="Démarrer le remorquage",
        default=False,
        help="Cocher pour passer directement à l'état 'Remorquage' après création",
    )
    create_intervention = fields.Boolean(
        string="Créer intervention maintenance",
        default=False,
        help="Cocher pour créer automatiquement une intervention de maintenance curative",
    )

    # =========================================================================
    # FIELDS - Responsible
    # =========================================================================
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        help="Utilisateur responsable du suivi de l'incident",
    )

    # =========================================================================
    # DEFAULT METHODS
    # =========================================================================
    @api.model
    def _default_vehicle_id(self):
        """Get vehicle from context if available."""
        return self.env.context.get("default_vehicle_id") or self.env.context.get("active_id") \
            if self.env.context.get("active_model") == "fleet.vehicle" else False

    # =========================================================================
    # ONCHANGE METHODS
    # =========================================================================
    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        """Auto-fill driver from vehicle."""
        if self.vehicle_id:
            self.driver_id = self.vehicle_id.driver_id
            # Suggest partners if available on vehicle
            if hasattr(self.vehicle_id, "tow_partner_ids") and self.vehicle_id.tow_partner_ids:
                self.towing_partner_id = self.vehicle_id.tow_partner_ids[:1]
            if hasattr(self.vehicle_id, "garage_partner_ids") and self.vehicle_id.garage_partner_ids:
                self.garage_partner_id = self.vehicle_id.garage_partner_ids[:1]

    @api.onchange("incident_type")
    def _onchange_incident_type(self):
        """Suggest priority based on incident type."""
        if self.incident_type == "accident":
            self.priority = "2"
        elif self.incident_type == "theft":
            self.priority = "3"
        elif self.incident_type == "breakdown":
            self.priority = "1"

    # =========================================================================
    # ACTION METHODS
    # =========================================================================
    def action_create_incident(self):
        """Create the incident ticket from wizard data."""
        self.ensure_one()

        # Validate required fields
        if not self.vehicle_id:
            raise UserError(_("Veuillez sélectionner un véhicule."))
        if not self.name:
            raise UserError(_("Veuillez saisir un titre pour l'incident."))

        # Prepare values for incident ticket
        incident_vals = {
            "name": self.name,
            "vehicle_id": self.vehicle_id.id,
            "driver_id": self.driver_id.id if self.driver_id else False,
            "company_id": self.company_id.id,
            "incident_type": self.incident_type,
            "incident_date": self.incident_date,
            "incident_location": self.incident_location,
            "description": self.description,
            "priority": self.priority,
            "responsible_id": self.responsible_id.id if self.responsible_id else False,
            "towing_partner_id": self.towing_partner_id.id if self.towing_partner_id else False,
            "garage_partner_id": self.garage_partner_id.id if self.garage_partner_id else False,
        }

        # Create the incident ticket
        incident = self.env["fleet.incident.ticket"].create(incident_vals)

        # Handle workflow options
        if self.start_towing and self.towing_partner_id:
            incident.action_start_towing()

        if self.create_intervention:
            try:
                incident.action_create_intervention()
            except UserError:
                # Maintenance module may not be available, continue anyway
                pass

        # Return action to view the created incident
        return {
            "type": "ir.actions.act_window",
            "name": _("Ticket d'incident"),
            "res_model": "fleet.incident.ticket",
            "res_id": incident.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_and_new(self):
        """Create incident and open wizard again for another."""
        self.action_create_incident()
        return {
            "type": "ir.actions.act_window",
            "name": _("Déclarer un incident"),
            "res_model": "fleet.incident.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_company_id": self.company_id.id,
                "default_responsible_id": self.responsible_id.id,
            },
        }
