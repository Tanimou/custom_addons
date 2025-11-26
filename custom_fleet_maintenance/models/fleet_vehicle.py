from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    # Field to check if vehicle is on mission (for button visibility)
    # This field may also be defined in custom_fleet_management if installed
    is_on_mission = fields.Boolean(
        string="En mission",
        compute="_compute_is_on_mission",
        store=False,
        help="Indique si le vehicule est actuellement en mission.",
    )

    @api.depends_context('uid')
    def _compute_is_on_mission(self):
        """Check if vehicle has active missions. Safe fallback if fleet.mission doesn't exist."""
        for vehicle in self:
            vehicle.is_on_mission = False
            # Check if fleet.mission model exists (custom_fleet_management installed)
            if 'fleet.mission' in self.env:
                active_mission = self.env['fleet.mission'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('state', 'in', ['confirmed', 'in_progress']),
                ], limit=1)
                vehicle.is_on_mission = bool(active_mission)

    # Add is_available field for this module (may be overridden if custom_fleet_management is installed)
    is_available = fields.Boolean(
        string='Disponible',
        compute='_compute_is_available',
        store=True,
        help="Indique si le véhicule est disponible (pas en mission ni en maintenance)"
    )

    @api.depends('maintenance_state', 'maintenance_history_ids.state')
    def _compute_is_available(self):
        """
        Compute vehicle availability based on maintenance state.
        If custom_fleet_management is installed, this extends its logic.
        """
        for vehicle in self:
            # Check if super() method exists (custom_fleet_management installed)
            # and call it first
            if hasattr(super(FleetVehicle, vehicle), '_compute_is_available'):
                super(FleetVehicle, vehicle)._compute_is_available()
            else:
                # Default: vehicle is available if active
                vehicle.is_available = vehicle.active if hasattr(vehicle, 'active') else True
            
            # Additional check: if maintenance_state is not operational, vehicle is not available
            if vehicle.maintenance_state != 'operational':
                vehicle.is_available = False
            
            # Also check for any active interventions
            active_interventions = vehicle.maintenance_history_ids.filtered(
                lambda i: i.state in ('submitted', 'in_progress')
            )
            if active_interventions:
                vehicle.is_available = False

    maintenance_state = fields.Selection(
        selection=[
            ("operational", "Fonctionnel"),
            ("maintenance", "En maintenance"),
            ("breakdown", "En panne"),
        ],
        string="Etat d'exploitation",
        default="operational",
        tracking=True,
    )
    maintenance_location_id = fields.Many2one(
        "stock.location",
        string="Emplacement de maintenance",
        tracking=True,
        help="Lieu ou le vehicule est stationne pendant l'intervention.",
    )
    km_actuel = fields.Float(string="Kilometrage actuel", tracking=True)
    next_preventive_date = fields.Date(string="Prochaine maintenance (date)")
    next_preventive_odometer = fields.Float(string="Prochaine maintenance (km)")
    maintenance_history_ids = fields.One2many(
        "fleet.maintenance.intervention",
        "vehicle_id",
        string="Historique des maintenances",
    )
    active_intervention_count = fields.Integer(
        string="Interventions ouvertes",
        compute="_compute_maintenance_counters",
    )
    preventive_intervention_count = fields.Integer(
        string="Preventions planifiees",
        compute="_compute_maintenance_counters",
    )

    def _compute_maintenance_counters(self):
        read_group_result = self.env["fleet.maintenance.intervention"].read_group(
            domain=[
                ("vehicle_id", "in", self.ids),
                ("state", "not in", ["done", "cancelled"]),
            ],
            fields=["vehicle_id", "intervention_type"],
            groupby=["vehicle_id", "intervention_type"],
        )
        counters = {}
        for data in read_group_result:
            vehicle_id = data.get("vehicle_id") and data["vehicle_id"][0]
            key = (vehicle_id, data.get("intervention_type"))
            counters[key] = data.get("__count", 0)
        for vehicle in self:
            vehicle.active_intervention_count = (
                counters.get((vehicle.id, "curative"), 0) + counters.get((vehicle.id, "preventive"), 0)
            )
            vehicle.preventive_intervention_count = counters.get((vehicle.id, "preventive"), 0)

    @api.constrains("km_actuel")
    def _check_km_actuel(self):
        for vehicle in self:
            if vehicle.km_actuel < 0:
                raise ValidationError(_("Le kilometrage doit etre positif."))
            if vehicle._origin and vehicle._origin.km_actuel and vehicle.km_actuel < vehicle._origin.km_actuel:
                raise ValidationError(_("Le kilometrage ne peut pas diminuer."))

    def action_open_maintenance_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenances du vehicule"),
            "res_model": "fleet.maintenance.intervention",
            "view_mode": "list,form,calendar,kanban",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {
                "default_vehicle_id": self.id,
                "default_driver_id": self.driver_id.id,
            },
        }

    def action_create_curative_intervention(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Creer une intervention"),
            "res_model": "fleet.maintenance.intervention",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_vehicle_id": self.id,
                "default_driver_id": self.driver_id.id,
                "default_intervention_type": "curative",
            },
        }

    def _update_preventive_dates(self):
        for vehicle in self:
            preventive = (
                vehicle.maintenance_history_ids.filtered(
                    lambda r: r.intervention_type == "preventive" and r.state == "done"
                )
                or vehicle.maintenance_history_ids.filtered(lambda r: r.intervention_type == "preventive")
            )
            if preventive:
                preventive = preventive.sorted(lambda r: r.close_date or r.scheduled_start, reverse=True)
                vehicle.next_preventive_date = preventive[0].next_planned_date
                vehicle.next_preventive_odometer = preventive[0].next_planned_odometer
