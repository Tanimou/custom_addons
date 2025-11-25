from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fleet_alert_offset_days = fields.Integer(
        string="Délai d'alerte (jours)",
        default=30,
        config_parameter="custom_fleet_maintenance.alert_offset_days",
    )
    fleet_weekly_digest_enabled = fields.Boolean(
        string="Envoyer le digest hebdomadaire",
        default=True,
        config_parameter="custom_fleet_maintenance.weekly_digest_enabled",
    )
    fleet_calendar_sync_enabled = fields.Boolean(
        string="Synchroniser automatiquement les évènements calendrier",
        default=True,
        config_parameter="custom_fleet_maintenance.calendar_sync_enabled",
    )
    fleet_default_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable par défaut",
        config_parameter="custom_fleet_maintenance.default_responsible_id",
    )
