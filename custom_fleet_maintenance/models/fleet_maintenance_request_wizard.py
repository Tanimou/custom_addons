from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FleetMaintenanceRequestWizard(models.TransientModel):
    _name = "fleet.maintenance.request.wizard"
    _description = "Assistant de demande de maintenance"

    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicule",
        required=True,
        domain="[('driver_id', '=', current_driver_id)]",
    )
    description = fields.Text(string="Description", required=True)
    current_driver_id = fields.Many2one(
        "res.partner",
        string="Conducteur",
        default=lambda self: self.env.user.partner_id,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        driver = self.env.user.partner_id
        vehicles = self.env["fleet.vehicle"].search([("driver_id", "=", driver.id)], limit=1)
        if vehicles:
            res.setdefault("vehicle_id", vehicles.id)
        return res

    def action_create_request(self):
        self.ensure_one()
        if self.vehicle_id.driver_id != self.env.user.partner_id:
            raise UserError(_("Vous ne pouvez declarer que pour votre propre vehicule."))
        intervention = self.env["fleet.maintenance.intervention"].create(
            {
                "intervention_type": "curative",
                "vehicle_id": self.vehicle_id.id,
                "driver_id": self.env.user.partner_id.id,
                "origin": "backend_wizard",
                "description": self.description,
                "state": "submitted",
            }
        )
        action = self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_action").read()[0]
        action["domain"] = [("id", "=", intervention.id)]
        action["views"] = [(self.env.ref("custom_fleet_maintenance.fleet_maintenance_intervention_view_form").id, "form")]
        action["res_id"] = intervention.id
        return action
