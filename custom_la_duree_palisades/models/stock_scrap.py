from odoo import models, fields, api


class StockScrapLoss(models.Model):
    _name = 'stock.scrap.loss'
    _description = 'Gestion des pertes'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nom',
        required=True,
    )

    loss_line_ids = fields.One2many(
        'stock.scrap.loss.line',
        'loss_id',
        string='Lignes de pertes',
    )

    start = fields.Datetime(
        string="Date de début",
        default=fields.Datetime.now,
        copy=False,
        tracking=True
    )
    end = fields.Datetime(string='Date de fin', copy=False, tracking=True)

    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        default=lambda self: self.env.user,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )

    total_price = fields.Monetary(
        string='Prix total',
        compute='_compute_total_price',
        store=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        related='company_id.currency_id',
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Valider'),
        ('cancel', 'Annuler'),
    ], string='État', default='draft')

    note = fields.Text(string='Note')

    @api.depends('loss_line_ids.total_price')
    def _compute_total_price(self):
        for loss in self:
            loss.total_price = sum(line.total_price for line in loss.loss_line_ids)

    def action_validate(self):
        self.write({'state': 'done'})


class StockScrapLoss(models.Model):
    _name = 'stock.scrap.loss.line'
    _description = 'Gestion des lignes de pertes'
    _rec_name = 'product_id'

    loss_id = fields.Many2one(
        'stock.scrap.loss',
        string='Perte',
    )

    product_id = fields.Many2one(
        'product.template',
        string='Article',
        required=True,
    )

    qty = fields.Float(
        string='Quantité',
        required=True,
    )

    state = fields.Selection(related='loss_id.state', string='État', store=True)

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unite de mesure',
        related='product_id.uom_id',
    )

    price_unit = fields.Monetary(
        string='Prix unitaire',  
    )

    total_price = fields.Monetary(
        string='Prix total',
        compute='_compute_total_price',
        store=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    scrap_reason_tag_ids = fields.Many2many(
        'stock.scrap.reason.tag',
        string='Raison de perte',
    )

    location_id = fields.Many2one(
        'stock.location',
        string='Emplacement',
    )


    date = fields.Datetime(
        string='Date',
        required=True,
        default=fields.Datetime.now,
    )


    @api.depends('qty', 'price_unit')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.qty * line.price_unit