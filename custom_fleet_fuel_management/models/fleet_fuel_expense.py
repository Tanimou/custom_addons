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
    purchase_order_id = fields.Many2one("purchase.order", string="Commande d'achat", copy=False)
    purchase_order_count = fields.Integer(compute="_compute_purchase_order_count", string="Nombre de commandes")
    batch_id = fields.Many2one("fleet.fuel.expense.batch", string="Lot d'import", ondelete="set null")
    import_hash = fields.Char(string="Hash import", copy=False, index=True)
    receipt_attachment = fields.Many2many(
        'ir.attachment',
        string='Justificatif',
        ondelete='cascade',
        help="Scan ou PDF du document"
    )
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

    @api.depends("purchase_order_id")
    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = 1 if record.purchase_order_id else 0

    @api.onchange('card_id')
    def _onchange_card_id(self):
        """Auto-fill vehicle and driver from fuel card."""
        if self.card_id:
            if self.card_id.vehicle_id:
                self.vehicle_id = self.card_id.vehicle_id
            if self.card_id.driver_id:
                self.driver_id = self.card_id.driver_id
        else:
            # Clear fields if card is removed
            self.vehicle_id = False
            self.driver_id = False

    @api.model
    def _get_or_create_fuel_product(self):
        """Get or create the 'Carburant' product for fuel expenses."""
        product = self.env['product.product'].search([
            ('name', '=', 'Carburant'),
        ], limit=1)
        
        if not product:
            # In Odoo 19, 'type' field is on product.template (not detailed_type)
            # Create via product.template to set the type correctly
            template = self.env['product.template'].sudo().create({
                'name': 'Carburant',
                'type': 'consu',
                'purchase_ok': True,
                'sale_ok': False,
            })
            product = template.product_variant_id
        return product

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

    # @api.constrains("receipt_attachment")
    # def _check_receipt_attachment(self):
    #     for expense in self:
    #         if not expense.receipt_attachment:
    #             raise ValidationError(_("Un justificatif est obligatoire pour enregistrer la dépense."))

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
        action = None
        for record in self:
            if record.state not in ("draft", "submitted"):
                raise UserError(_("Seules les dépenses brouillon ou soumises peuvent être validées."))
            service.spend_amount(record.card_id, record.amount)
            record.state = "validated"
            record.validated_by_id = self.env.user
            record.validated_date = fields.Datetime.now()
            record.message_post(body=_("Dépense validée et déduite du solde."))
            
            # Create Purchase Order and get redirect action
            if record.station_partner_id:
                action = record.action_create_purchase_order()
        
        # Return the action to redirect to PO form (for last/single expense)
        if action:
            return action
        return True

    def action_create_purchase_order(self):
        """Create a purchase order for the fuel expense."""
        self.ensure_one()
        
        if not self.station_partner_id:
            raise UserError(_("Veuillez définir une station service avant de créer une commande."))
        
        product = self._get_or_create_fuel_product()
        
        # Use liters if available, otherwise quantity = 1 with total amount
        if self.liter_qty and self.liter_qty > 0:
            qty = self.liter_qty
            price = self.price_per_liter
        else:
            qty = 1
            price = self.amount
        
        order_vals = {
            "partner_id": self.station_partner_id.id,
            "origin": self.name,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "name": _("Carburant - %s", self.name),
                "product_qty": qty,
                "product_uom_id": product.uom_id.id,  # Odoo 19: renamed from product_uom
                "price_unit": price,
                "date_planned": self.expense_date or fields.Date.today(),
                "analytic_distribution": self.analytic_account_id and {str(self.analytic_account_id.id): 100} or False,
            })],
        }
        
        order = self.env["purchase.order"].sudo().create(order_vals)
        self.purchase_order_id = order.id
        self.message_post(body=_("Commande d'achat %s créée.", order.name))
        
        # Return action to redirect to PO form
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["res_id"] = order.id
        action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        return action

    def action_view_purchase_order(self):
        """Open the linked purchase order."""
        self.ensure_one()
        if not self.purchase_order_id:
            return False
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["res_id"] = self.purchase_order_id.id
        action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        return action

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
