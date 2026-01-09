from odoo import models, fields, api,_, SUPERUSER_ID

class ProjectProjectInherit(models.Model):
    _inherit = "project.project"


    cycle_duration = fields.Integer('Durée du cycle (en jours)', default=45)
    picking_id = fields.Many2one('stock.picking', string="Dossier de livraison")
    lot_strip = fields.Many2one('stock.lot', string="Lot/Bande")
    Chicken_coop = fields.Many2one('stock.location', string="Poulailler")
    purchase_id = fields.Many2one('purchase.order', string="Bons de commande fournisseur", copy=False, readonly=True)
    number_chicks_received = fields.Integer('Nombre de poussin reçu', default=0)
    number_dead_chicks = fields.Integer('Nombre de poussin morts', default=0)
    number_live_chicks = fields.Integer('Nombre de poussin vivant', compute='_compute_live_chicks', store=True)
    date_chicks_received = fields.Date('Date de réception des poussins')
    mortality_rate = fields.Float('Taux de mortalité (%)', compute='_compute_mortality_rate', store=True)
    type_operation = fields.Selection(related='picking_id.type_operation', string="Type reception", store=True)
    egg_collection_ids = fields.One2many('egg.collection.project', 'project_id', string="Collecte d'oeufs")


    @api.depends('number_chicks_received', 'number_dead_chicks')
    def _compute_live_chicks(self):
        for record in self:
            record.number_live_chicks = record.number_chicks_received - record.number_dead_chicks
            if record.number_live_chicks < 0:
                record.number_live_chicks = 0

    @api.depends('number_chicks_received', 'number_dead_chicks')
    def _compute_mortality_rate(self):
        for record in self:
            if record.number_chicks_received > 0:
                record.mortality_rate = (record.number_dead_chicks / record.number_chicks_received) * 100
            else:
                record.mortality_rate = 0.0