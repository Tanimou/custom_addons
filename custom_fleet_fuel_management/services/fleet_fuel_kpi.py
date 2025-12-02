# -*- coding: utf-8 -*-
"""Fleet Fuel KPI Service.

AbstractModel service for calculating fuel consumption KPIs:
- L/100km consumption calculation
- Budget variance analysis
- Alert level determination
- Monthly summary generation

Per REQ-005/TASK-009 of feature-fuel-management-1.md.
"""
import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FleetFuelKPIService(models.AbstractModel):
    """Service for calculating fleet fuel KPIs.

    This AbstractModel provides reusable methods for:
    - Computing L/100km fuel consumption
    - Computing budget variance
    - Determining alert levels
    - Generating monthly summaries
    - Batch processing for cron jobs

    Usage:
        service = self.env["fleet.fuel.kpi.service"]
        l_per_100km = service.compute_l_per_100km(liters=50.0, distance=500.0)
        variance = service.compute_budget_variance(actual=1200.0, budget=1000.0)
        alert = service.determine_alert_level(variance_pct=15.0)
    """

    _name = "fleet.fuel.kpi.service"
    _description = "Service de calcul des KPIs carburant"

    # -------------------------------------------------------------------------
    # CONSUMPTION CALCULATIONS
    # -------------------------------------------------------------------------
    @api.model
    def compute_l_per_100km(self, liters, distance):
        """Compute fuel consumption in L/100km.

        Args:
            liters: Total liters consumed (float)
            distance: Distance traveled in km (float)

        Returns:
            float: L/100km consumption, or 0.0 if distance is 0
        """
        if not distance or distance <= 0:
            return 0.0
        if not liters or liters <= 0:
            return 0.0
        return (liters / distance) * 100

    @api.model
    def compute_avg_price_per_liter(self, amount, liters):
        """Compute average price per liter.

        Args:
            amount: Total monetary amount (float)
            liters: Total liters (float)

        Returns:
            float: Average price per liter, or 0.0 if liters is 0
        """
        if not liters or liters <= 0:
            return 0.0
        if not amount:
            return 0.0
        return amount / liters

    # -------------------------------------------------------------------------
    # BUDGET VARIANCE
    # -------------------------------------------------------------------------
    @api.model
    def compute_budget_variance(self, actual, budget):
        """Compute budget variance.

        Args:
            actual: Actual spent amount (float)
            budget: Budgeted amount (float)

        Returns:
            tuple: (variance_amount, variance_pct)
                - variance_amount: actual - budget (negative = saving)
                - variance_pct: percentage of budget (0 if no budget)
        """
        if not budget or budget == 0:
            return (0.0, 0.0)
        variance_amount = (actual or 0.0) - budget
        variance_pct = (variance_amount / budget) * 100
        return (variance_amount, variance_pct)

    # -------------------------------------------------------------------------
    # ALERT LEVEL
    # -------------------------------------------------------------------------
    @api.model
    def determine_alert_level(self, variance_pct, threshold=None):
        """Determine alert level based on variance percentage.

        Uses threshold from ir.config_parameter if not provided.

        Args:
            variance_pct: Variance percentage (float)
            threshold: Optional override for threshold (float)
                       Default comes from fleet_fuel.variance_threshold_pct

        Returns:
            str: Alert level ('ok', 'warning', 'critical')
        """
        if threshold is None:
            ICP = self.env["ir.config_parameter"].sudo()
            threshold = float(ICP.get_param("fleet_fuel.variance_threshold_pct", "10.0"))

        variance = abs(variance_pct)
        if variance <= threshold:
            return "ok"
        elif variance <= threshold * 2:
            return "warning"
        else:
            return "critical"

    @api.model
    def get_alert_threshold(self):
        """Get the configured variance threshold percentage.

        Returns:
            float: Threshold percentage from config
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return float(ICP.get_param("fleet_fuel.variance_threshold_pct", "10.0"))

    # -------------------------------------------------------------------------
    # SUMMARY GENERATION
    # -------------------------------------------------------------------------
    @api.model
    def generate_monthly_summaries(self, period_start=None, period_end=None,
                                    vehicle_ids=None, card_ids=None,
                                    company_id=None, force=False):
        """Generate monthly fuel summaries for the given period.

        This method creates or updates fleet.fuel.monthly.summary records
        for each vehicle/card combination with validated expenses.

        Args:
            period_start: Start date (defaults to first day of previous month)
            period_end: End date (defaults to last day of previous month)
            vehicle_ids: List of vehicle IDs to process (None = all)
            card_ids: List of card IDs to process (None = all)
            company_id: Company ID (defaults to current company)
            force: If True, regenerate even if summary exists

        Returns:
            recordset: Created/updated fleet.fuel.monthly.summary records
        """
        Summary = self.env["fleet.fuel.monthly.summary"]
        Expense = self.env["fleet.fuel.expense"]

        # Default to previous month
        if not period_start or not period_end:
            today = fields.Date.context_today(self)
            first_of_month = today.replace(day=1)
            period_end = first_of_month - timedelta(days=1)
            period_start = period_end.replace(day=1)

        company_id = company_id or self.env.company.id
        _logger.info(
            "Generating fuel summaries for period %s to %s, company %s",
            period_start, period_end, company_id
        )

        # Find all unique (vehicle, card) combinations with expenses
        expense_domain = [
            ("expense_date", ">=", period_start),
            ("expense_date", "<=", period_end),
            ("state", "=", "validated"),
            ("company_id", "=", company_id),
        ]
        if vehicle_ids:
            expense_domain.append(("vehicle_id", "in", vehicle_ids))
        if card_ids:
            expense_domain.append(("card_id", "in", card_ids))

        # Group by vehicle and card
        expense_groups = Expense.read_group(
            expense_domain,
            ["vehicle_id", "card_id", "driver_id"],
            ["vehicle_id", "card_id", "driver_id"],
            lazy=False,
        )

        created_summaries = Summary
        for group in expense_groups:
            vehicle_id = group["vehicle_id"][0] if group["vehicle_id"] else False
            card_id = group["card_id"][0] if group["card_id"] else False
            driver_id = group["driver_id"][0] if group["driver_id"] else False

            if not vehicle_id and not card_id:
                continue

            # Check for existing summary
            existing_domain = [
                ("period_start", "=", period_start),
                ("period_end", "=", period_end),
                ("company_id", "=", company_id),
            ]
            if vehicle_id:
                existing_domain.append(("vehicle_id", "=", vehicle_id))
            else:
                existing_domain.append(("vehicle_id", "=", False))
            if card_id:
                existing_domain.append(("card_id", "=", card_id))
            else:
                existing_domain.append(("card_id", "=", False))

            existing = Summary.search(existing_domain, limit=1)

            if existing and not force:
                _logger.debug(
                    "Summary already exists for vehicle %s, card %s, skipping",
                    vehicle_id, card_id
                )
                created_summaries |= existing
                continue

            if existing and force:
                # Update existing summary
                existing.write({
                    "driver_id": driver_id,
                })
                existing.action_recalculate()
                created_summaries |= existing
                _logger.info("Updated summary %s", existing.name)
            else:
                # Create new summary
                vals = {
                    "period_start": period_start,
                    "period_end": period_end,
                    "vehicle_id": vehicle_id,
                    "card_id": card_id,
                    "driver_id": driver_id,
                    "company_id": company_id,
                    "currency_id": self.env.company.currency_id.id,
                }
                new_summary = Summary.create(vals)
                new_summary.action_auto_fill_odometer()
                created_summaries |= new_summary
                _logger.info("Created summary %s", new_summary.name)

        _logger.info("Generated %d fuel summaries", len(created_summaries))
        return created_summaries

    @api.model
    def generate_summaries_for_all_companies(self, period_start=None, period_end=None):
        """Generate summaries for all companies (cron job entry point).

        Args:
            period_start: Optional start date
            period_end: Optional end date

        Returns:
            recordset: All created/updated summaries
        """
        companies = self.env["res.company"].search([])
        all_summaries = self.env["fleet.fuel.monthly.summary"]

        for company in companies:
            summaries = self.with_company(company).generate_monthly_summaries(
                period_start=period_start,
                period_end=period_end,
                company_id=company.id,
            )
            all_summaries |= summaries

        return all_summaries

    # -------------------------------------------------------------------------
    # ALERT DETECTION
    # -------------------------------------------------------------------------
    @api.model
    def detect_critical_summaries(self, days_back=30):
        """Find summaries with critical or warning alerts.

        Args:
            days_back: Look back this many days for period_end

        Returns:
            recordset: fleet.fuel.monthly.summary with alerts
        """
        Summary = self.env["fleet.fuel.monthly.summary"]
        cutoff_date = fields.Date.context_today(self) - timedelta(days=days_back)

        return Summary.search([
            ("period_end", ">=", cutoff_date),
            ("alert_level", "in", ["warning", "critical"]),
            ("state", "!=", "closed"),
        ])

    @api.model
    def send_alert_notifications(self):
        """Send email notifications for critical summaries.

        This is called by cron job. Uses mail template
        'custom_fleet_fuel_management.mail_template_fleet_fuel_summary_alert'.
        """
        critical_summaries = self.detect_critical_summaries()
        if not critical_summaries:
            _logger.info("No critical fuel summaries to notify")
            return

        template = self.env.ref(
            "custom_fleet_fuel_management.mail_template_fleet_fuel_summary_alert",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Mail template 'mail_template_fleet_fuel_summary_alert' not found")
            return

        for summary in critical_summaries:
            try:
                template.send_mail(summary.id, force_send=True)
                _logger.info("Sent alert for summary %s", summary.name)
            except Exception as e:
                _logger.exception("Failed to send alert for summary %s: %s", summary.name, e)

    # -------------------------------------------------------------------------
    # REPORTING HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def get_consumption_stats(self, vehicle_id=None, card_id=None,
                               period_start=None, period_end=None,
                               company_id=None):
        """Get aggregated consumption statistics.

        Args:
            vehicle_id: Filter by vehicle
            card_id: Filter by card
            period_start: Start date
            period_end: End date
            company_id: Company ID

        Returns:
            dict: Aggregated statistics
        """
        Expense = self.env["fleet.fuel.expense"]
        domain = [("state", "=", "validated")]

        if company_id:
            domain.append(("company_id", "=", company_id))
        else:
            domain.append(("company_id", "=", self.env.company.id))
        if vehicle_id:
            domain.append(("vehicle_id", "=", vehicle_id))
        if card_id:
            domain.append(("card_id", "=", card_id))
        if period_start:
            domain.append(("expense_date", ">=", period_start))
        if period_end:
            domain.append(("expense_date", "<=", period_end))

        data = Expense.read_group(domain, ["amount:sum", "liter_qty:sum"], [])

        total_amount = data[0]["amount"] if data else 0.0
        total_liters = data[0]["liter_qty"] if data else 0.0
        expense_count = Expense.search_count(domain)

        return {
            "total_amount": total_amount or 0.0,
            "total_liters": total_liters or 0.0,
            "expense_count": expense_count,
            "avg_price_per_liter": self.compute_avg_price_per_liter(total_amount, total_liters),
        }

    @api.model
    def get_top_consuming_vehicles(self, limit=10, period_start=None,
                                    period_end=None, company_id=None):
        """Get top fuel consuming vehicles.

        Args:
            limit: Number of vehicles to return
            period_start: Start date
            period_end: End date
            company_id: Company ID

        Returns:
            list: List of dicts with vehicle info and consumption
        """
        Expense = self.env["fleet.fuel.expense"]
        domain = [("state", "=", "validated")]

        if company_id:
            domain.append(("company_id", "=", company_id))
        else:
            domain.append(("company_id", "=", self.env.company.id))
        if period_start:
            domain.append(("expense_date", ">=", period_start))
        if period_end:
            domain.append(("expense_date", "<=", period_end))

        grouped = Expense.read_group(
            domain,
            ["vehicle_id", "amount:sum", "liter_qty:sum"],
            ["vehicle_id"],
            orderby="amount desc",
            limit=limit,
        )

        result = []
        for g in grouped:
            if g["vehicle_id"]:
                result.append({
                    "vehicle_id": g["vehicle_id"][0],
                    "vehicle_name": g["vehicle_id"][1],
                    "total_amount": g["amount"] or 0.0,
                    "total_liters": g["liter_qty"] or 0.0,
                    "expense_count": g["vehicle_id_count"],
                })
        return result

    @api.model
    def get_monthly_trend(self, vehicle_id=None, months=12, company_id=None):
        """Get monthly fuel consumption trend.

        Args:
            vehicle_id: Optional vehicle filter
            months: Number of months to look back
            company_id: Company ID

        Returns:
            list: List of dicts with month and consumption data
        """
        Expense = self.env["fleet.fuel.expense"]
        today = fields.Date.context_today(self)

        result = []
        for i in range(months - 1, -1, -1):
            month_date = today - relativedelta(months=i)
            period_start = month_date.replace(day=1)
            if i == 0:
                period_end = today
            else:
                next_month = period_start + relativedelta(months=1)
                period_end = next_month - timedelta(days=1)

            domain = [
                ("state", "=", "validated"),
                ("expense_date", ">=", period_start),
                ("expense_date", "<=", period_end),
            ]
            if company_id:
                domain.append(("company_id", "=", company_id))
            else:
                domain.append(("company_id", "=", self.env.company.id))
            if vehicle_id:
                domain.append(("vehicle_id", "=", vehicle_id))

            data = Expense.read_group(domain, ["amount:sum", "liter_qty:sum"], [])
            result.append({
                "month": period_start.strftime("%Y-%m"),
                "month_label": period_start.strftime("%b %Y"),
                "total_amount": data[0]["amount"] if data else 0.0,
                "total_liters": data[0]["liter_qty"] if data else 0.0,
            })

        return result
