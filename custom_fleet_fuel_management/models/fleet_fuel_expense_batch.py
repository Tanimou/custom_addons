# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class FleetFuelExpenseBatch(models.Model):
    _name = "fleet.fuel.expense.batch"
    _description = "Lot d'import de dépenses carburant"
    _order = "create_date desc"

    name = fields.Char(string="Référence", required=True, default="Lot d'import")
    import_filename = fields.Char(string="Fichier")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("processing", "En cours"),
            ("done", "Terminé"),
            ("error", "En erreur"),
        ],
        default="draft",
    )
    company_id = fields.Many2one("res.company", string="Société", default=lambda self: self.env.company, required=True)
    user_id = fields.Many2one("res.users", string="Créé par", default=lambda self: self.env.user)
    line_ids = fields.One2many("fleet.fuel.expense.batch.line", "batch_id", string="Lignes importées")
    expense_ids = fields.One2many("fleet.fuel.expense", "batch_id", string="Dépenses")
    line_count = fields.Integer(string="Nombre de lignes", compute="_compute_counts", store=True)
    error_count = fields.Integer(string="Erreurs", compute="_compute_counts", store=True)
    success_count = fields.Integer(string="Succès", compute="_compute_counts", store=True)
    log_message = fields.Text(string="Journal")
    started_at = fields.Datetime(string="Début")
    finished_at = fields.Datetime(string="Fin")

    @api.depends("line_ids.state")
    def _compute_counts(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.error_count = len(batch.line_ids.filtered(lambda l: l.state == "error"))
            batch.success_count = len(batch.line_ids.filtered(lambda l: l.state == "done"))

    def action_view_expenses(self):
        self.ensure_one()
        action = self.env.ref("custom_fleet_fuel_management.action_fleet_fuel_expense", raise_if_not_found=False)
        if not action:
            return False
        result = action.read()[0]
        domain = result.get("domain", [])
        domain = list(domain) if isinstance(domain, (list, tuple)) else []
        domain.append(("batch_id", "=", self.id))
        result["domain"] = domain
        result.setdefault("context", {})
        result["context"].update({"default_batch_id": self.id})
        return result

    def log_line(self, **vals):
        self.ensure_one()
        defaults = {
            "batch_id": self.id,
            "sequence": len(self.line_ids) + 1,
        }
        defaults.update(vals)
        return self.env["fleet.fuel.expense.batch.line"].create(defaults)

    def set_processing(self):
        self.write({"state": "processing", "started_at": fields.Datetime.now()})

    def set_finished(self, has_error=False):
        state = "error" if has_error else "done"
        self.write({"state": state, "finished_at": fields.Datetime.now()})


class FleetFuelExpenseBatchLine(models.Model):
    _name = "fleet.fuel.expense.batch.line"
    _description = "Détail d'import d'une dépense carburant"
    _order = "sequence"

    batch_id = fields.Many2one("fleet.fuel.expense.batch", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Ligne")
    state = fields.Selection(
        [("done", "Créée"), ("skipped", "Ignorée"), ("error", "Erreur")],
        default="done",
    )
    message = fields.Text(string="Message")
    expense_id = fields.Many2one("fleet.fuel.expense", string="Dépense liée")
    import_hash = fields.Char(string="Hash")