# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FleetFuelRecharge(models.Model):
    _name = "fleet.fuel.recharge"
    _description = "Recharge carte carburant"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "recharge_date desc, name desc"

    name = fields.Char(string="Référence", copy=False, tracking=True)
    card_id = fields.Many2one("fleet.fuel.card", string="Carte", required=True, tracking=True)
    company_id = fields.Many2one(
        related="card_id.company_id",
        store=True,
        readonly=True,
        string="Société",
    )
    currency_id = fields.Many2one(related="card_id.currency_id", store=True, readonly=True)
    amount = fields.Monetary(string="Montant", required=True, tracking=True)
    recharge_date = fields.Date(
        string="Date de recharge",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
        help="Date de la demande de recharge",
    )
    description = fields.Text(string="Motif")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumise"),
            ("approved", "Approuvée"),
            ("posted", "Comptabilisée"),
            ("cancelled", "Annulée"),
        ],
        default="draft",
        tracking=True,
    )
    requested_by_id = fields.Many2one("res.users", string="Demandeur", default=lambda self: self.env.user, tracking=True)
    approved_by_id = fields.Many2one("res.users", string="Validateur", tracking=True)
    posted_by_id = fields.Many2one("res.users", string="Comptabilisé par", tracking=True)
    approval_date = fields.Datetime(string="Date approbation")
    posting_date = fields.Datetime(string="Date comptabilisation")

    _sql_constraints = [("fleet_fuel_recharge_amount_check", "CHECK(amount > 0)", "Le montant doit être positif.")]

    def _balance_service(self):
        return self.env["fleet.fuel.balance.service"]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("fleet.fuel.recharge") or _("Nouvelle recharge")
        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            if record.state != "draft":
                continue
            record.state = "submitted"
            record.message_post(body=_("Recharge soumise"))
            self._balance_service().reserve_amount(record.card_id, record.amount)
        return True

    def action_approve(self):
        for record in self:
            if record.state not in ("submitted", "draft"):
                continue
            record.state = "approved"
            record.approval_date = fields.Datetime.now()
            record.approved_by_id = self.env.user
            record.message_post(body=_("Recharge approuvée"))
        return True

    def action_post(self):
        for record in self:
            if record.state not in ("approved",):
                raise UserError(_("La recharge doit être approuvée avant publication."))
            record.state = "posted"
            record.posting_date = fields.Datetime.now()
            record.posted_by_id = self.env.user
            service = self._balance_service()
            service.release_amount(record.card_id, record.amount)
            service.apply_delta(record.card_id, record.amount)
            record.message_post(body=_("Recharge comptabilisée"))
        return True

    def action_cancel(self):
        for record in self:
            if record.state == "posted":
                raise UserError(_("Impossible d'annuler une recharge comptabilisée."))
            if record.state in ("submitted", "approved"):
                self._balance_service().release_amount(record.card_id, record.amount)
            record.state = "cancelled"
            record.message_post(body=_("Recharge annulée"))
        return True