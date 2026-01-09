from odoo import models, fields, api
from odoo.exceptions import UserError

class StockScrapLossReportWizard(models.TransientModel):
    _name = 'stock.scrap.loss.report.wizard'
    _description = 'Wizard Rapport des pertes'

    date_from = fields.Date(string='Date de début', required=True)
    date_to = fields.Date(string='Date de fin', required=True)
    scrap_loss_ids = fields.Many2many(
        'stock.scrap.loss.line', string='Pertes', compute='_compute_scrap_lines_ids'
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Valider'),
        ('cancel', 'Annuler'),
    ], string='État', default='draft')


    @api.depends('date_from', 'date_to')
    def _compute_scrap_lines_ids(self):
        for record in self:
            scraps = self.env['stock.scrap.loss.line'].search([
                ('date', '>=', record.date_from),
                ('date', '<=', record.date_to),
                ('state', '=', record.state),
            ], order='date asc')
            record.scrap_loss_ids = scraps

    def action_print_report(self):
        self.ensure_one()
        if not self.scrap_loss_ids:
            raise UserError("Aucune donnée trouvée pour la période sélectionnée.")

        return self.env.ref('custom_la_duree_palisades.action_report_scrap_loss').report_action(self)
