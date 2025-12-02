# -*- coding: utf-8 -*-
"""Fleet Fuel Management - Configuration Settings.

Extends res.config.settings to add fleet fuel management configuration.
Per REQ-006/TASK-010 of feature-fuel-management-1.md.

Configuration Parameters stored in ir.config_parameter:
- fleet_fuel.budget_journal_id: Default journal for fuel budget
- fleet_fuel.variance_threshold_pct: Alert threshold percentage
- fleet_fuel.alert_offset_days: Days offset for expiration alerts
- fleet_fuel.alert_manager_ids: Comma-separated user IDs for alerts
- fleet_fuel.auto_generate_summary: Enable automatic monthly summary generation
- fleet_fuel.summary_day_of_month: Day to generate monthly summaries
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Fleet fuel management configuration settings."""

    _inherit = "res.config.settings"

    # -------------------------------------------------------------------------
    # BUDGET CONFIGURATION
    # -------------------------------------------------------------------------
    fleet_fuel_budget_journal_id = fields.Many2one(
        "account.journal",
        string="Journal budget carburant",
        help="Journal comptable par défaut pour les écritures de budget carburant",
        compute="_compute_fleet_fuel_budget_journal_id",
        inverse="_inverse_fleet_fuel_budget_journal_id",
    )

    # -------------------------------------------------------------------------
    # ALERT CONFIGURATION (simple fields with config_parameter)
    # -------------------------------------------------------------------------
    fleet_fuel_variance_threshold_pct = fields.Float(
        string="Seuil d'alerte (%)",
        default=10.0,
        config_parameter="fleet_fuel.variance_threshold_pct",
        help=(
            "Seuil de variance budgétaire en pourcentage.\n"
            "- OK: écart <= seuil\n"
            "- Attention: seuil < écart <= 2x seuil\n"
            "- Critique: écart > 2x seuil"
        ),
    )

    fleet_fuel_alert_offset_days = fields.Integer(
        string="Offset alertes (jours)",
        default=5,
        config_parameter="fleet_fuel.alert_offset_days",
        help=(
            "Nombre de jours avant la date d'expiration pour déclencher les alertes.\n"
            "Exemple: 5 = alerte 5 jours avant expiration de la carte"
        ),
    )

    # -------------------------------------------------------------------------
    # ALERT MANAGERS (Many2many requires compute/inverse pattern)
    # -------------------------------------------------------------------------
    fleet_fuel_alert_manager_ids = fields.Many2many(
        "res.users",
        string="Responsables alertes",
        relation="fleet_fuel_config_alert_manager_rel",
        column1="config_id",
        column2="user_id",
        compute="_compute_fleet_fuel_alert_manager_ids",
        inverse="_inverse_fleet_fuel_alert_manager_ids",
        help="Utilisateurs qui recevront les notifications d'alerte carburant",
    )

    # -------------------------------------------------------------------------
    # AUTOMATION SETTINGS
    # -------------------------------------------------------------------------
    fleet_fuel_auto_generate_summary = fields.Boolean(
        string="Génération automatique des synthèses",
        default=True,
        config_parameter="fleet_fuel.auto_generate_summary",
        help="Génère automatiquement les synthèses mensuelles via cron",
    )

    fleet_fuel_summary_day_of_month = fields.Integer(
        string="Jour de génération mensuelle",
        default=1,
        config_parameter="fleet_fuel.summary_day_of_month",
        help="Jour du mois où les synthèses sont générées (1-28)",
    )

    fleet_fuel_require_receipt = fields.Boolean(
        string="Justificatif obligatoire",
        default=True,
        config_parameter="fleet_fuel.require_receipt",
        help="Rend le justificatif obligatoire pour valider les dépenses",
    )

    fleet_fuel_track_odometer = fields.Boolean(
        string="Suivi odomètre",
        default=True,
        config_parameter="fleet_fuel.track_odometer",
        help="Active le suivi de l'odomètre sur les dépenses carburant",
    )

    # -------------------------------------------------------------------------
    # COMPUTE / INVERSE for Many2one (Budget Journal)
    # -------------------------------------------------------------------------
    @api.depends("company_id")
    def _compute_fleet_fuel_budget_journal_id(self):
        """Get budget journal from ir.config_parameter."""
        ICP = self.env["ir.config_parameter"].sudo()
        journal_id_str = ICP.get_param("fleet_fuel.budget_journal_id", "")
        journal_id = int(journal_id_str) if journal_id_str else False
        for record in self:
            if journal_id:
                journal = self.env["account.journal"].browse(journal_id).exists()
                record.fleet_fuel_budget_journal_id = journal if journal else False
            else:
                record.fleet_fuel_budget_journal_id = False

    def _inverse_fleet_fuel_budget_journal_id(self):
        """Store budget journal ID in ir.config_parameter."""
        ICP = self.env["ir.config_parameter"].sudo()
        for record in self:
            journal_id = record.fleet_fuel_budget_journal_id.id if record.fleet_fuel_budget_journal_id else ""
            ICP.set_param("fleet_fuel.budget_journal_id", str(journal_id) if journal_id else "")

    # -------------------------------------------------------------------------
    # COMPUTE / INVERSE for Many2many (Alert Managers)
    # -------------------------------------------------------------------------
    @api.depends("company_id")
    def _compute_fleet_fuel_alert_manager_ids(self):
        """Get alert managers from ir.config_parameter.

        Stores comma-separated user IDs in the parameter.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        manager_ids_str = ICP.get_param("fleet_fuel.alert_manager_ids", "")
        manager_ids = []
        if manager_ids_str:
            try:
                manager_ids = [int(x.strip()) for x in manager_ids_str.split(",") if x.strip()]
            except ValueError:
                _logger.warning("Invalid fleet_fuel.alert_manager_ids format: %s", manager_ids_str)
                manager_ids = []

        for record in self:
            if manager_ids:
                users = self.env["res.users"].browse(manager_ids).exists()
                record.fleet_fuel_alert_manager_ids = users
            else:
                record.fleet_fuel_alert_manager_ids = False

    def _inverse_fleet_fuel_alert_manager_ids(self):
        """Store alert manager IDs in ir.config_parameter as comma-separated string."""
        ICP = self.env["ir.config_parameter"].sudo()
        for record in self:
            if record.fleet_fuel_alert_manager_ids:
                manager_ids_str = ",".join(str(uid) for uid in record.fleet_fuel_alert_manager_ids.ids)
            else:
                manager_ids_str = ""
            ICP.set_param("fleet_fuel.alert_manager_ids", manager_ids_str)

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    @api.model
    def get_fleet_fuel_alert_managers(self):
        """Utility method to get alert managers from anywhere.

        Returns:
            recordset: res.users recordset of alert managers
        """
        ICP = self.env["ir.config_parameter"].sudo()
        manager_ids_str = ICP.get_param("fleet_fuel.alert_manager_ids", "")
        if not manager_ids_str:
            return self.env["res.users"]
        try:
            manager_ids = [int(x.strip()) for x in manager_ids_str.split(",") if x.strip()]
            return self.env["res.users"].browse(manager_ids).exists()
        except ValueError:
            return self.env["res.users"]

    @api.model
    def get_fleet_fuel_budget_journal(self):
        """Utility method to get budget journal from anywhere.

        Returns:
            recordset: account.journal record or empty
        """
        ICP = self.env["ir.config_parameter"].sudo()
        journal_id_str = ICP.get_param("fleet_fuel.budget_journal_id", "")
        if not journal_id_str:
            return self.env["account.journal"]
        try:
            journal_id = int(journal_id_str)
            return self.env["account.journal"].browse(journal_id).exists()
        except ValueError:
            return self.env["account.journal"]

    @api.model
    def get_fleet_fuel_variance_threshold(self):
        """Get variance threshold percentage.

        Returns:
            float: Threshold percentage
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return float(ICP.get_param("fleet_fuel.variance_threshold_pct", "10.0"))

    @api.model
    def get_fleet_fuel_alert_offset_days(self):
        """Get alert offset days.

        Returns:
            int: Number of days before expiration for alerts
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return int(ICP.get_param("fleet_fuel.alert_offset_days", "5"))