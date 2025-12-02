# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FleetFuelMonthlySummary(models.Model):
    """Monthly fuel consumption summary per vehicle/card.

    Consolidates expenses and recharges for a given period, calculates KPIs
    (L/100km, budget variance), and determines alert levels for monitoring.
    Per REQ-005/TASK-009 of feature-fuel-management-1.md.
    """

    _name = "fleet.fuel.monthly.summary"
    _description = "Synthèse mensuelle carburant"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_end desc, vehicle_id, card_id"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # BASIC FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Référence",
        required=True,
        copy=False,
        tracking=True,
        help="Identifiant unique de la synthèse mensuelle",
    )
    period_start = fields.Date(
        string="Début période",
        required=True,
        tracking=True,
        index=True,
    )
    period_end = fields.Date(
        string="Fin période",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company.id,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    # -------------------------------------------------------------------------
    # RELATIONS
    # -------------------------------------------------------------------------
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Véhicule",
        tracking=True,
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    card_id = fields.Many2one(
        "fleet.fuel.card",
        string="Carte carburant",
        tracking=True,
        index=True,
        domain="[('company_id', '=', company_id)]",
    )
    driver_id = fields.Many2one(
        "hr.employee",
        string="Conducteur",
        tracking=True,
        index=True,
        help="Conducteur principal sur la période",
    )
    expense_ids = fields.One2many(
        "fleet.fuel.expense",
        compute="_compute_linked_records",
        string="Dépenses",
        help="Dépenses validées sur la période",
    )
    recharge_ids = fields.One2many(
        "fleet.fuel.recharge",
        compute="_compute_linked_records",
        string="Recharges",
        help="Recharges postées sur la période",
    )

    # -------------------------------------------------------------------------
    # CONSUMPTION TOTALS
    # -------------------------------------------------------------------------
    total_amount = fields.Monetary(
        string="Montant total",
        compute="_compute_consumption_totals",
        store=True,
        currency_field="currency_id",
        tracking=True,
        help="Somme des montants des dépenses validées",
    )
    total_liter = fields.Float(
        string="Litres total",
        compute="_compute_consumption_totals",
        store=True,
        digits=(12, 2),
        tracking=True,
        help="Somme des litres des dépenses validées",
    )
    expense_count = fields.Integer(
        string="Nb dépenses",
        compute="_compute_consumption_totals",
        store=True,
        help="Nombre de dépenses validées sur la période",
    )
    total_recharge_amount = fields.Monetary(
        string="Total recharges",
        compute="_compute_consumption_totals",
        store=True,
        currency_field="currency_id",
        help="Somme des recharges postées sur la période",
    )
    recharge_count = fields.Integer(
        string="Nb recharges",
        compute="_compute_consumption_totals",
        store=True,
        help="Nombre de recharges postées sur la période",
    )

    # -------------------------------------------------------------------------
    # ODOMETER & DISTANCE
    # -------------------------------------------------------------------------
    odometer_start = fields.Float(
        string="Odomètre début",
        digits=(12, 1),
        help="Valeur odomètre au début de la période",
    )
    odometer_end = fields.Float(
        string="Odomètre fin",
        digits=(12, 1),
        help="Valeur odomètre à la fin de la période",
    )
    distance_traveled = fields.Float(
        string="Distance parcourue",
        compute="_compute_distance_kpi",
        store=True,
        digits=(12, 1),
        help="Distance calculée (odomètre fin - odomètre début)",
    )

    # -------------------------------------------------------------------------
    # KPI FIELDS
    # -------------------------------------------------------------------------
    avg_consumption_per_100km = fields.Float(
        string="Conso. L/100km",
        compute="_compute_distance_kpi",
        store=True,
        digits=(6, 2),
        tracking=True,
        help="Consommation moyenne en litres pour 100 km",
    )
    avg_price_per_liter = fields.Monetary(
        string="Prix moyen / litre",
        compute="_compute_avg_price",
        store=True,
        currency_field="currency_id",
        digits=(10, 4),
        help="Prix moyen par litre sur la période",
    )
    budget_amount = fields.Monetary(
        string="Budget prévu",
        currency_field="currency_id",
        help="Montant budgété pour la période (manuel ou depuis ligne budgétaire)",
    )
    budget_variance = fields.Monetary(
        string="Écart budgétaire",
        compute="_compute_budget_kpi",
        store=True,
        currency_field="currency_id",
        tracking=True,
        help="Écart = Montant dépensé - Budget prévu (négatif = économie)",
    )
    variance_pct = fields.Float(
        string="Écart %",
        compute="_compute_budget_kpi",
        store=True,
        digits=(6, 2),
        tracking=True,
        help="Écart budgétaire en pourcentage du budget",
    )
    alert_level = fields.Selection(
        [
            ("ok", "OK"),
            ("warning", "Attention"),
            ("critical", "Critique"),
        ],
        string="Niveau d'alerte",
        compute="_compute_alert_level",
        store=True,
        tracking=True,
        help="OK: écart < seuil; Warning: écart entre seuil et 2x seuil; Critical: > 2x seuil",
    )

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("confirmed", "Confirmée"),
            ("closed", "Clôturée"),
        ],
        string="Statut",
        default="draft",
        tracking=True,
        help="Brouillon: en cours de calcul; Confirmée: validée; Clôturée: archivée",
    )
    notes = fields.Html(string="Notes")

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        (
            "fleet_fuel_summary_period_check",
            "CHECK(period_end >= period_start)",
            "La date de fin doit être >= à la date de début.",
        ),
        (
            "fleet_fuel_summary_unique",
            "unique(company_id, vehicle_id, card_id, period_start, period_end)",
            "Une synthèse existe déjà pour ce véhicule/carte sur cette période.",
        ),
    ]

    # -------------------------------------------------------------------------
    # DATABASE INDEXES (via init hook)
    # -------------------------------------------------------------------------
    def init(self):
        """Create composite indexes for performance per TASK-009."""
        super().init()
        # Index for period + vehicle queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_summary_period_vehicle_idx
            ON fleet_fuel_monthly_summary (period_start, period_end, vehicle_id)
            WHERE vehicle_id IS NOT NULL
        """)
        # Index for period + card queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_summary_period_card_idx
            ON fleet_fuel_monthly_summary (period_start, period_end, card_id)
            WHERE card_id IS NOT NULL
        """)
        # Index for alert monitoring
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_summary_alert_idx
            ON fleet_fuel_monthly_summary (alert_level, state)
            WHERE alert_level IN ('warning', 'critical') AND state != 'closed'
        """)
        _logger.info("Fleet fuel summary indexes created/verified")

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS
    # -------------------------------------------------------------------------
    def _compute_linked_records(self):
        """Compute linked expenses and recharges for the period."""
        Expense = self.env["fleet.fuel.expense"]
        Recharge = self.env["fleet.fuel.recharge"]
        for summary in self:
            domain = [
                ("expense_date", ">=", summary.period_start),
                ("expense_date", "<=", summary.period_end),
                ("state", "=", "validated"),
                ("company_id", "=", summary.company_id.id),
            ]
            if summary.vehicle_id:
                domain.append(("vehicle_id", "=", summary.vehicle_id.id))
            if summary.card_id:
                domain.append(("card_id", "=", summary.card_id.id))
            summary.expense_ids = Expense.search(domain)

            recharge_domain = [
                ("recharge_date", ">=", summary.period_start),
                ("recharge_date", "<=", summary.period_end),
                ("state", "=", "posted"),
                ("company_id", "=", summary.company_id.id),
            ]
            if summary.card_id:
                recharge_domain.append(("card_id", "=", summary.card_id.id))
            summary.recharge_ids = Recharge.search(recharge_domain)

    @api.depends("period_start", "period_end", "vehicle_id", "card_id", "company_id")
    def _compute_consumption_totals(self):
        """Calculate expense and recharge totals from linked records."""
        Expense = self.env["fleet.fuel.expense"]
        Recharge = self.env["fleet.fuel.recharge"]
        for summary in self:
            if not (summary.period_start and summary.period_end and summary.company_id):
                summary.total_amount = 0.0
                summary.total_liter = 0.0
                summary.expense_count = 0
                summary.total_recharge_amount = 0.0
                summary.recharge_count = 0
                continue

            # Build expense domain
            expense_domain = [
                ("expense_date", ">=", summary.period_start),
                ("expense_date", "<=", summary.period_end),
                ("state", "=", "validated"),
                ("company_id", "=", summary.company_id.id),
            ]
            if summary.vehicle_id:
                expense_domain.append(("vehicle_id", "=", summary.vehicle_id.id))
            if summary.card_id:
                expense_domain.append(("card_id", "=", summary.card_id.id))

            expense_data = Expense.read_group(
                expense_domain,
                ["amount:sum", "liter_qty:sum"],
                [],
            )
            if expense_data:
                summary.total_amount = expense_data[0].get("amount", 0.0) or 0.0
                summary.total_liter = expense_data[0].get("liter_qty", 0.0) or 0.0
            else:
                summary.total_amount = 0.0
                summary.total_liter = 0.0
            summary.expense_count = Expense.search_count(expense_domain)

            # Build recharge domain
            recharge_domain = [
                ("recharge_date", ">=", summary.period_start),
                ("recharge_date", "<=", summary.period_end),
                ("state", "=", "posted"),
                ("company_id", "=", summary.company_id.id),
            ]
            if summary.card_id:
                recharge_domain.append(("card_id", "=", summary.card_id.id))

            recharge_data = Recharge.read_group(
                recharge_domain,
                ["amount:sum"],
                [],
            )
            if recharge_data:
                summary.total_recharge_amount = recharge_data[0].get("amount", 0.0) or 0.0
            else:
                summary.total_recharge_amount = 0.0
            summary.recharge_count = Recharge.search_count(recharge_domain)

    @api.depends("odometer_start", "odometer_end", "total_liter")
    def _compute_distance_kpi(self):
        """Calculate distance traveled and L/100km consumption."""
        for summary in self:
            distance = 0.0
            if summary.odometer_end and summary.odometer_start:
                distance = summary.odometer_end - summary.odometer_start
            summary.distance_traveled = max(distance, 0.0)

            # Calculate L/100km
            if summary.distance_traveled > 0 and summary.total_liter > 0:
                summary.avg_consumption_per_100km = (summary.total_liter / summary.distance_traveled) * 100
            else:
                summary.avg_consumption_per_100km = 0.0

    @api.depends("total_amount", "total_liter")
    def _compute_avg_price(self):
        """Calculate average price per liter."""
        for summary in self:
            if summary.total_liter > 0:
                summary.avg_price_per_liter = summary.total_amount / summary.total_liter
            else:
                summary.avg_price_per_liter = 0.0

    @api.depends("total_amount", "budget_amount")
    def _compute_budget_kpi(self):
        """Calculate budget variance and percentage."""
        for summary in self:
            if summary.budget_amount:
                summary.budget_variance = summary.total_amount - summary.budget_amount
                summary.variance_pct = (summary.budget_variance / summary.budget_amount) * 100
            else:
                summary.budget_variance = 0.0
                summary.variance_pct = 0.0

    @api.depends("variance_pct")
    def _compute_alert_level(self):
        """Determine alert level based on variance percentage.

        Uses threshold from config (fleet_fuel_variance_threshold_pct).
        - OK: variance <= threshold
        - Warning: threshold < variance <= 2*threshold
        - Critical: variance > 2*threshold
        """
        ICP = self.env["ir.config_parameter"].sudo()
        threshold = float(ICP.get_param("fleet_fuel.variance_threshold_pct", "10.0"))
        for summary in self:
            variance = abs(summary.variance_pct)
            if variance <= threshold:
                summary.alert_level = "ok"
            elif variance <= threshold * 2:
                summary.alert_level = "warning"
            else:
                summary.alert_level = "critical"

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence reference on creation."""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fleet.fuel.monthly.summary") or _("Nouvelle synthèse")
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("currency_id"):
                vals["currency_id"] = self.env.company.currency_id.id
        return super().create(vals_list)

    @api.constrains("period_start", "period_end")
    def _check_period_dates(self):
        """Validate period dates."""
        for summary in self:
            if summary.period_end < summary.period_start:
                raise ValidationError(_("La date de fin doit être supérieure ou égale à la date de début."))

    @api.constrains("odometer_start", "odometer_end")
    def _check_odometer_values(self):
        """Validate odometer readings."""
        for summary in self:
            if summary.odometer_start and summary.odometer_start < 0:
                raise ValidationError(_("L'odomètre de début ne peut pas être négatif."))
            if summary.odometer_end and summary.odometer_end < 0:
                raise ValidationError(_("L'odomètre de fin ne peut pas être négatif."))
            if summary.odometer_start and summary.odometer_end:
                if summary.odometer_end < summary.odometer_start:
                    raise ValidationError(_("L'odomètre de fin doit être supérieur à l'odomètre de début."))

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """Confirm the summary after review."""
        for summary in self:
            if summary.state != "draft":
                continue
            summary.state = "confirmed"
            summary.message_post(body=_("Synthèse confirmée"))
        return True

    def action_close(self):
        """Close/archive the summary."""
        for summary in self:
            if summary.state != "confirmed":
                continue
            summary.state = "closed"
            summary.message_post(body=_("Synthèse clôturée"))
        return True

    def action_reset_to_draft(self):
        """Reset to draft for re-calculation."""
        for summary in self:
            if summary.state == "closed":
                continue
            summary.state = "draft"
            summary.message_post(body=_("Synthèse remise en brouillon"))
        return True

    def action_recalculate(self):
        """Force recalculation of all computed fields."""
        for summary in self:
            # Trigger recomputation by invalidating cache
            summary.invalidate_recordset(["total_amount", "total_liter", "expense_count",
                                          "total_recharge_amount", "recharge_count",
                                          "avg_consumption_per_100km", "avg_price_per_liter",
                                          "budget_variance", "variance_pct", "alert_level",
                                          "distance_traveled"])
            # Re-read to trigger compute
            summary.read(["total_amount", "total_liter", "expense_count",
                          "total_recharge_amount", "recharge_count"])
            summary.message_post(body=_("Synthèse recalculée"))
        return True

    def action_auto_fill_odometer(self):
        """Auto-fill odometer values from expenses in the period."""
        for summary in self:
            if not summary.vehicle_id:
                continue
            Expense = self.env["fleet.fuel.expense"]
            domain = [
                ("expense_date", ">=", summary.period_start),
                ("expense_date", "<=", summary.period_end),
                ("state", "=", "validated"),
                ("vehicle_id", "=", summary.vehicle_id.id),
                ("odometer", ">", 0),
            ]
            expenses = Expense.search(domain, order="expense_date asc, odometer asc")
            if expenses:
                first_odo = expenses[0].odometer
                last_odo = expenses[-1].odometer
                summary.write({
                    "odometer_start": first_odo,
                    "odometer_end": last_odo,
                })
                summary.message_post(body=_("Odomètres renseignés automatiquement depuis les dépenses."))
        return True

    # -------------------------------------------------------------------------
    # CRON METHODS
    # -------------------------------------------------------------------------
    @api.model
    def cron_compute_monthly_summary(self):
        """Cron job to generate/update monthly summaries.

        Called daily by ir.cron. Generates summaries for the previous month
        on the configured day of month, or updates existing summaries.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        auto_generate = ICP.get_param("fleet_fuel.auto_generate_summary", "True")
        if auto_generate.lower() not in ("true", "1", "yes"):
            _logger.info("Auto summary generation disabled, skipping")
            return

        today = fields.Date.context_today(self)
        summary_day = int(ICP.get_param("fleet_fuel.summary_day_of_month", "1"))

        # Only run on the configured day
        if today.day != summary_day:
            _logger.debug("Today is not summary day (%s), skipping", summary_day)
            return

        _logger.info("Running monthly fuel summary generation cron")
        kpi_service = self.env["fleet.fuel.kpi.service"]
        try:
            summaries = kpi_service.generate_summaries_for_all_companies()
            _logger.info("Generated %d fuel summaries", len(summaries))
        except Exception as e:
            _logger.exception("Error generating fuel summaries: %s", e)

    @api.model
    def cron_send_fuel_alerts(self):
        """Cron job to send alert notifications.

        Called daily. Sends emails for summaries with warning/critical alerts.
        """
        _logger.info("Running fuel alert notification cron")
        kpi_service = self.env["fleet.fuel.kpi.service"]
        try:
            kpi_service.send_alert_notifications()
        except Exception as e:
            _logger.exception("Error sending fuel alerts: %s", e)