from datetime import timedelta

from odoo import api, fields, models


class FleetMaintenancePlan(models.Model):
    _name = "fleet.maintenance.plan"
    _description = "Plan de maintenance préventive"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        default=lambda self: self.env.company,
    )
    vehicle_model_ids = fields.Many2many("fleet.vehicle.model", string="Modèles concernés")
    vehicle_ids = fields.Many2many(
        "fleet.vehicle",
        string="Véhicules suivis",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    interval_type = fields.Selection(
        selection=[
            ("time", "Temps"),
            ("odometer", "Kilométrage"),
            ("hybrid", "Mixte"),
        ],
        default="time",
        required=True,
    )
    interval_value = fields.Integer(string="Fréquence", default=1)
    interval_unit = fields.Selection(
        selection=[("days", "Jour(s)"), ("weeks", "Semaine(s)"), ("months", "Mois")],
        default="months",
        required=True,
    )
    odometer_interval = fields.Float(string="Seuil kilométrique (km)")
    instruction_html = fields.Html(string="Instructions", sanitize_style=True)
    plan_line_ids = fields.One2many("fleet.maintenance.plan.line", "plan_id", string="Lignes")
    color = fields.Integer()
    tolerance_days = fields.Integer(string="Tolérance jours", default=0)
    tolerance_km = fields.Float(string="Tolérance km", default=0.0)
    active = fields.Boolean(default=True)

    assignment_type = fields.Selection(
        selection=[("model", "Par modèle"), ("vehicle", "Par véhicule")],
        default="model",
    )

    def action_generate_lines(self):
        self.ensure_one()
        vehicles = self._get_target_vehicles()
        line_values = []
        for vehicle in vehicles:
            if vehicle.company_id and vehicle.company_id != self.company_id:
                continue
            if self.plan_line_ids.filtered(lambda l: l.vehicle_id == vehicle):
                continue
            next_date = fields.Date.context_today(self) + self._get_interval_delta()
            line_values.append(
                {
                    "plan_id": self.id,
                    "vehicle_id": vehicle.id,
                    "company_id": vehicle.company_id.id or self.company_id.id,
                    "next_due_date": next_date,
                    "next_due_odometer": vehicle.km_actuel + (self.odometer_interval or 0.0),
                }
            )
        if line_values:
            self.env["fleet.maintenance.plan.line"].create(line_values)
        return True

    def _get_target_vehicles(self):
        self.ensure_one()
        if self.assignment_type == "vehicle":
            return self.vehicle_ids
        return self.env["fleet.vehicle"].search(
            [
                ("model_id", "in", self.vehicle_model_ids.ids),
                ("company_id", "in", [False, self.company_id.id]),
            ]
        )

    def _get_interval_delta(self):
        self.ensure_one()
        interval_value = self.interval_value or 1
        if self.interval_unit == "days":
            return timedelta(days=interval_value)
        if self.interval_unit == "weeks":
            return timedelta(weeks=interval_value)
        return timedelta(days=interval_value * 30)

    @api.model
    def cron_generate_preventive_interventions(self):
        plan_line_model = self.env["fleet.maintenance.plan.line"].sudo()
        config = self.env["ir.config_parameter"].sudo()
        alert_offset = int(config.get_param("custom_fleet_maintenance.alert_offset_days", 30))
        today = fields.Date.context_today(self)
        alert_date = today + timedelta(days=alert_offset)
        domain = [
            ("plan_id.active", "=", True),
            ("vehicle_id", "!=", False),
            "|",
            ("next_due_date", "!=", False),
            ("next_due_odometer", "!=", False),
        ]
        candidate_lines = plan_line_model.search(domain)
        for line in candidate_lines:
            if line._has_open_preventive_intervention():
                continue
            if line.next_due_date and line.next_due_date <= alert_date:
                line._create_preventive_intervention()
                continue
            if line.next_due_odometer and line.vehicle_id.km_actuel and line.vehicle_id.km_actuel >= line.next_due_odometer:
                line._create_preventive_intervention()


class FleetMaintenancePlanLine(models.Model):
    _name = "fleet.maintenance.plan.line"
    _description = "Ligne de plan de maintenance"
    _order = "next_due_date, vehicle_id"

    plan_id = fields.Many2one("fleet.maintenance.plan", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="plan_id.company_id", store=True, readonly=True)
    vehicle_id = fields.Many2one("fleet.vehicle", string="Véhicule", required=True)
    responsible_id = fields.Many2one("res.users", string="Responsable")
    next_due_date = fields.Date(string="Prochaine date due")
    next_due_odometer = fields.Float(string="Prochain kilométrage")
    last_execution_id = fields.Many2one("fleet.maintenance.intervention", string="Dernière intervention")
    active = fields.Boolean(default=True)
    state = fields.Selection(
        selection=[("ok", "À jour"), ("due", "À planifier"), ("late", "En retard")],
        compute="_compute_state",
        store=True,
    )

    @api.depends(
        "next_due_date",
        "next_due_odometer",
        "vehicle_id.km_actuel",
        "last_execution_id.state",
        "plan_id.tolerance_days",
        "plan_id.tolerance_km",
    )
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for line in self:
            state = "ok"
            tolerance_days = line.plan_id.tolerance_days or 0
            tolerance_km = line.plan_id.tolerance_km or 0.0
            if line.next_due_date:
                if line.next_due_date + timedelta(days=tolerance_days) < today:
                    state = "late"
                elif line.next_due_date <= today:
                    state = "due"
            if line.next_due_odometer and line.vehicle_id.km_actuel:
                if line.vehicle_id.km_actuel >= (line.next_due_odometer + tolerance_km):
                    state = "late"
                elif line.vehicle_id.km_actuel >= line.next_due_odometer and state == "ok":
                    state = "due"
            if line.last_execution_id and line.last_execution_id.state not in ("done", "cancelled"):
                state = "due"
            line.state = state

    def _has_open_preventive_intervention(self):
        self.ensure_one()
        return bool(
            self.env["fleet.maintenance.intervention"].search_count(
                [
                    ("plan_line_id", "=", self.id),
                    ("state", "not in", ["done", "cancelled"]),
                ],
                limit=1,
            )
        )

    def _create_preventive_intervention(self):
        self.ensure_one()
        vals = self._prepare_intervention_vals()
        intervention = self.env["fleet.maintenance.intervention"].sudo().create(vals)
        self.last_execution_id = intervention
        self._compute_next_threshold()
        return intervention

    def _prepare_intervention_vals(self):
        self.ensure_one()
        planned_date = self.next_due_date or fields.Date.context_today(self)
        follower_users = self.plan_id.message_partner_ids.mapped("user_ids")
        fallback_user_id = follower_users[:1].id if follower_users else False
        values = {
            "intervention_type": "preventive",
            "vehicle_id": self.vehicle_id.id,
            "company_id": self.company_id.id,
            "name": False,  # séquence gérée en create
            "plan_line_id": self.id,
            "scheduled_start": planned_date,
            "scheduled_end": planned_date,
            "next_planned_date": planned_date + self.plan_id._get_interval_delta(),
            "next_planned_odometer": self.next_due_odometer and self.next_due_odometer + (self.plan_id.odometer_interval or 0.0),
            "description": self.plan_id.instruction_html,
            "responsible_id": self.responsible_id.id or fallback_user_id,
        }
        if self.plan_id.interval_type in ("odometer", "hybrid") and self.plan_id.odometer_interval:
            values.setdefault("next_planned_odometer", (self.next_due_odometer or self.vehicle_id.km_actuel) + self.plan_id.odometer_interval)
        return values

    def _compute_next_threshold(self):
        self.ensure_one()
        next_date = (self.next_due_date or fields.Date.context_today(self)) + self.plan_id._get_interval_delta()
        self.next_due_date = next_date
        if self.plan_id.odometer_interval:
            self.next_due_odometer = (self.next_due_odometer or self.vehicle_id.km_actuel or 0.0) + self.plan_id.odometer_interval
