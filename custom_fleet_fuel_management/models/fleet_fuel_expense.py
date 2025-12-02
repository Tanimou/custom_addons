# -*- coding: utf-8 -*-
import hashlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FleetFuelExpense(models.Model):
    _name = "fleet.fuel.expense"
    _description = "Dépense carburant"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expense_date desc, name desc"

    name = fields.Char(string="Référence", copy=False, tracking=True)
    card_id = fields.Many2one(
        "fleet.fuel.card",
        string="Carte carburant",
        required=True,
        tracking=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Véhicule",
        required=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    driver_id = fields.Many2one(
        "hr.employee",
        string="Conducteur",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    expense_date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    odometer = fields.Float(string="Odomètre", help="Valeur de l'odomètre au moment de la dépense.")
    liter_qty = fields.Float(string="Litres", tracking=True)
    price_per_liter = fields.Monetary(
        string="Prix / litre",
        compute="_compute_price_per_liter",
        store=True,
        currency_field="currency_id",
    )
    amount = fields.Monetary(string="Montant", required=True, tracking=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company.id,
        index=True,
        tracking=True,
    )
    notes = fields.Html(string="Notes")
    station_partner_id = fields.Many2one(
        "res.partner",
        string="Station service",
        domain="[('supplier_rank', '>', 0)]",
    )
    analytic_account_id = fields.Many2one("account.analytic.account", string="Centre de coûts")
    budget_line_id = fields.Many2one("budget.line", string="Ligne budgétaire")
    batch_id = fields.Many2one("fleet.fuel.expense.batch", string="Lot d'import", ondelete="set null")
    import_hash = fields.Char(string="Hash import", copy=False, index=True)
    receipt_attachment = fields.Binary(string="Justificatif", attachment=True, required=True)
    receipt_filename = fields.Char(string="Nom du justificatif")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumise"),
            ("validated", "Validée"),
            ("rejected", "Rejetée"),
        ],
        string="Statut",
        default="draft",
        tracking=True,
    )
    submitted_by_id = fields.Many2one("res.users", string="Soumis par", readonly=True)
    validated_by_id = fields.Many2one("res.users", string="Validé par", readonly=True)
    validated_date = fields.Datetime(string="Date validation")

    _sql_constraints = [
        ("fleet_fuel_expense_amount_check", "CHECK(amount > 0)", "Le montant doit être positif."),
        ("fleet_fuel_expense_liter_check", "CHECK(liter_qty >= 0)", "Les litres doivent être positifs."),
        ("fleet_fuel_expense_import_hash_unique", "unique(import_hash)", "Cette dépense a déjà été importée."),
    ]

    def _balance_service(self):
        return self.env["fleet.fuel.balance.service"]

    @api.model
    def _make_import_hash(self, card_id, expense_date, amount, liter_qty):
        if not all([card_id, expense_date, amount]):
            return False
        if hasattr(expense_date, "isoformat"):
            expense_date = expense_date.isoformat()
        amount = float(amount)
        liter_qty = liter_qty or 0.0
        key = f"{card_id}-{expense_date}-{amount}-{liter_qty}"
        return hashlib.sha1(key.encode()).hexdigest()

    @api.depends("amount", "liter_qty")
    def _compute_price_per_liter(self):
        for expense in self:
            if expense.liter_qty:
                expense.price_per_liter = expense.amount / expense.liter_qty
            else:
                expense.price_per_liter = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fleet.fuel.expense") or _("Nouvelle dépense")
            if not vals.get("currency_id"):
                vals["currency_id"] = self.env.company.currency_id.id
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            card_id = vals.get("card_id")
            if card_id:
                card = self.env["fleet.fuel.card"].browse(card_id)
                if not vals.get("vehicle_id") and card.vehicle_id:
                    vals["vehicle_id"] = card.vehicle_id.id
                if not vals.get("driver_id") and card.driver_id:
                    vals["driver_id"] = card.driver_id.id
                if not vals.get("company_id"):
                    vals["company_id"] = card.company_id.id
                if not vals.get("currency_id"):
                    vals["currency_id"] = card.currency_id.id
            if not vals.get("import_hash"):
                vals["import_hash"] = self._make_import_hash(
                    vals.get("card_id"),
                    vals.get("expense_date"),
                    vals.get("amount"),
                    vals.get("liter_qty"),
                )
        records = super().create(vals_list)
        for record in records.filtered(lambda e: e.state == "draft"):
            if not record.submitted_by_id:
                record.submitted_by_id = self.env.user
            if not record.import_hash:
                record.import_hash = self._make_import_hash(record.card_id.id, record.expense_date, record.amount, record.liter_qty)
        return records

    def write(self, vals):
        if "card_id" in vals or "vehicle_id" in vals:
            for expense in self:
                if expense.state not in ("draft", "submitted"):
                    raise UserError(_("Impossible de modifier la carte ou le véhicule d'une dépense validée."))
        res = super().write(vals)
        watched = {"card_id", "expense_date", "amount", "liter_qty"}
        if watched.intersection(vals):
            for expense in self:
                expense.import_hash = self._make_import_hash(
                    expense.card_id.id,
                    expense.expense_date,
                    expense.amount,
                    expense.liter_qty,
                )
        return res

    def unlink(self):
        for record in self:
            if record.state not in ("draft", "rejected"):
                raise UserError(_("Seules les dépenses brouillon ou rejetées peuvent être supprimées."))
        return super().unlink()

    @api.constrains("card_id", "vehicle_id")
    def _check_card_vehicle_company(self):
        for expense in self:
            if expense.card_id and expense.vehicle_id and expense.card_id.vehicle_id:
                if expense.card_id.vehicle_id != expense.vehicle_id:
                    raise ValidationError(_("Le véhicule de la dépense doit correspondre à celui de la carte."))
            if expense.card_id and expense.company_id and expense.card_id.company_id != expense.company_id:
                raise ValidationError(_("La société de la dépense doit correspondre à celle de la carte."))

    @api.constrains("receipt_attachment")
    def _check_receipt_attachment(self):
        for expense in self:
            if not expense.receipt_attachment:
                raise ValidationError(_("Un justificatif est obligatoire pour enregistrer la dépense."))

    @api.constrains("odometer")
    def _check_odometer_positive(self):
        for expense in self:
            if expense.odometer and expense.odometer < 0:
                raise ValidationError(_("La valeur d'odomètre doit être positive."))

    def action_submit(self):
        for record in self:
            if record.state != "draft":
                continue
            record.state = "submitted"
            record.submitted_by_id = record.submitted_by_id or self.env.user
            record.message_post(body=_("Dépense soumise"))
        return True

    def action_validate(self):
        service = self._balance_service()
        for record in self:
            if record.state not in ("draft", "submitted"):
                raise UserError(_("Seules les dépenses brouillon ou soumises peuvent être validées."))
            service.spend_amount(record.card_id, record.amount)
            record.state = "validated"
            record.validated_by_id = self.env.user
            record.validated_date = fields.Datetime.now()
            record.message_post(body=_("Dépense validée et déduite du solde."))
        return True

    def action_reject(self, reason=None):
        for record in self:
            if record.state not in ("draft", "submitted"):
                raise UserError(_("Impossible de rejeter une dépense déjà validée."))
            record.state = "rejected"
            body = reason or _("Dépense rejetée")
            record.message_post(body=body)
        return True

    def action_reset_to_draft(self):
        for record in self:
            if record.state not in ("rejected",):
                raise UserError(_("Seules les dépenses rejetées peuvent être remises en brouillon."))
            record.state = "draft"
        return True
