from odoo import api, fields, models


class FleetMaintenancePartLine(models.Model):
    _name = "fleet.maintenance.part.line"
    _description = "Lignes de coût de maintenance"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    intervention_id = fields.Many2one(
        "fleet.maintenance.intervention",
        string="Intervention",
        required=True,
        ondelete="cascade",
    )
    cost_type = fields.Selection(
        selection=[
            ("part", "Pièce détachée"),
            ("labor", "Main-d'œuvre"),
            ("subcontract", "Sous-traitance"),
            ("other", "Autre"),
        ],
        string="Type de coût",
        default="part",
        required=True,
    )
    product_id = fields.Many2one("product.product", string="Article")
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantité", default=1.0)
    uom_id = fields.Many2one("uom.uom", string="Unité")
    unit_price = fields.Monetary(string="Prix unitaire")
    currency_id = fields.Many2one(
        related="intervention_id.currency_id",
        store=True,
        readonly=True,
    )
    subtotal = fields.Monetary(string="Sous-total", compute="_compute_amounts", store=True)
    analytic_account_id = fields.Many2one("account.analytic.account", string="Compte analytique")
    vendor_id = fields.Many2one("res.partner", string="Prestataire", domain="[('supplier_rank', '>', 0)]")

    @api.depends("quantity", "unit_price")
    def _compute_amounts(self):
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.unit_price or 0.0)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.description = line.product_id.display_name
            if not line.uom_id:
                line.uom_id = line.product_id.uom_id
            if not line.unit_price:
                line.unit_price = line.product_id.standard_price
