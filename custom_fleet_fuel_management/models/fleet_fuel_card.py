# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class FleetFuelCard(models.Model):
    _name = "fleet.fuel.card"
    _description = "Carte carburant"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Référence", tracking=True, copy=False)
    card_uid = fields.Char(string="Numéro carte", required=True, copy=False, tracking=True)
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Véhicule",
        required=True,
        tracking=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    driver_id = fields.Many2one(
        "hr.employee",
        string="Conducteur",
        tracking=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    fuel_type = fields.Selection(
        [
            ("petrol", "Essence"),
            ("diesel", "Diesel"),
            ("electric", "Électrique"),
            ("hybrid", "Hybride"),
            ("other", "Autre"),
        ],
        string="Type de carburant",
        default="diesel",
        tracking=True,
    )
    activation_date = fields.Date(string="Date d'activation", tracking=True)
    expiration_date = fields.Date(string="Date d'expiration", tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Devise",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    balance_amount = fields.Monetary(string="Solde disponible", tracking=True)
    pending_amount = fields.Monetary(string="Montant en attente", tracking=True)
    available_amount = fields.Monetary(
        string="Solde utilisable", compute="_compute_available_amount", store=True, currency_field="currency_id",
        help="Montant réellement disponible pour les dépenses = Solde disponible - Montant en attente"
    )
    max_daily_amount = fields.Monetary(string="Plafond quotidien", currency_field="currency_id")
    max_month_amount = fields.Monetary(string="Plafond mensuel", currency_field="currency_id")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("active", "Active"),
            ("suspended", "Suspendue"),
            ("expired", "Expirée"),
        ],
        default="draft",
        string="Statut",
        tracking=True,
    )
    recharge_ids = fields.One2many("fleet.fuel.recharge", "card_id", string="Recharges")
    expense_ids = fields.One2many("fleet.fuel.expense", "card_id", string="Dépenses")
    attachment_count = fields.Integer(compute="_compute_attachment_count", string="Pièces jointes")
    alert_state = fields.Selection(
        [("ok", "OK"), ("warning", "Alerte"), ("critical", "Critique")],
        default="ok",
        string="Niveau d'alerte",
    )

    _sql_constraints = [("fleet_fuel_card_uid_unique", "unique(card_uid)", "Le numéro de carte doit être unique.")]

    @api.depends("balance_amount", "pending_amount")
    def _compute_available_amount(self):
        for card in self:
            card.available_amount = (card.balance_amount or 0.0) - (card.pending_amount or 0.0)

    def _compute_attachment_count(self):
        """Compute attachment count for each card."""
        attachment_model = self.env["ir.attachment"]
        for card in self:
            card.attachment_count = attachment_model.search_count(
                [
                    ("res_model", "=", card._name),
                    ("res_id", "=", card.id),
                ]
            )

    @api.constrains("activation_date", "expiration_date")
    def _check_dates(self):
        for card in self:
            if card.activation_date and card.expiration_date and card.expiration_date < card.activation_date:
                raise ValidationError(_("La date d'expiration doit être postérieure à l'activation."))

    @api.constrains("balance_amount")
    def _check_balance(self):
        for card in self:
            if card.balance_amount < 0:
                raise ValidationError(_("Le solde d'une carte ne peut pas être négatif."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fleet.fuel.card") or _("Nouvelle carte")
            if not vals.get("currency_id"):
                vals["currency_id"] = self.env.company.currency_id.id
            vehicle_id = vals.get("vehicle_id")
            if vehicle_id and not vals.get("driver_id"):
                vehicle = self.env["fleet.vehicle"].browse(vehicle_id)
                vals["driver_id"] = vehicle.driver_id.id
        records = super().create(vals_list)
        for card in records.filtered(lambda c: c.state == "draft"):
            card.message_subscribe(partner_ids=card._get_default_followers())
        return records

    def _get_default_followers(self):
        managers = self.env.ref("custom_fleet_fuel_management.group_fleet_fuel_manager", raise_if_not_found=False)
        return managers.user_ids.mapped("partner_id").ids if managers else []

    def action_activate(self):
        today = fields.Date.context_today(self)
        for card in self:
            if not card.activation_date:
                card.activation_date = today
            card.state = "active"
        return True

    def action_suspend(self):
        for card in self:
            card.state = "suspended"
        return True

    def action_mark_expired(self):
        today = fields.Date.context_today(self)
        for card in self:
            card.state = "expired"
            card.expiration_date = card.expiration_date or today
        return True

    def action_view_recharges(self):
        self.ensure_one()
        action = self.env.ref("custom_fleet_fuel_management.action_fleet_fuel_recharge", raise_if_not_found=False)
        if not action:
            return False
        action = action.read()[0]
        action["domain"] = [("card_id", "=", self.id)]
        eval_ctx = {"uid": self.env.uid, "user": self.env.user}
        ctx = safe_eval(action.get("context", "{}"), eval_ctx) if isinstance(action.get("context"), str) else dict(action.get("context") or {})
        ctx.update({"default_card_id": self.id, "default_company_id": self.company_id.id})
        action["context"] = ctx
        return action

    def action_view_expenses(self):
        self.ensure_one()
        action = self.env.ref("custom_fleet_fuel_management.action_fleet_fuel_expense", raise_if_not_found=False)
        if not action:
            return False
        action = action.read()[0]
        action["domain"] = [("card_id", "=", self.id)]
        eval_ctx = {"uid": self.env.uid, "user": self.env.user}
        ctx = safe_eval(action.get("context", "{}"), eval_ctx) if isinstance(action.get("context"), str) else dict(action.get("context") or {})
        ctx.update({"default_card_id": self.id, "default_vehicle_id": self.vehicle_id.id})
        action["context"] = ctx
        return action

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pièces jointes"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,tree,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
            "target": "current",
        }