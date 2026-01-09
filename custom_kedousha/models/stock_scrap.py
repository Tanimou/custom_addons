from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class StockScrapInherit(models.Model):
    _inherit = "stock.scrap"

    project_id = fields.Many2one('project.project', string="Projet/Cycle d'élevage", copy=False)
    def action_validate(self):
        """Validation du rebut + mise à jour des poussins liés."""
        res = super(StockScrapInherit, self).action_validate()
        projects = self.env['project.project'].search([('lot_strip', '=', self.lot_id.id), ('Chicken_coop', '=', self.location_id.id)])
        if projects:
            for project in projects:
                project.number_dead_chicks += self.scrap_qty
                project._compute_live_chicks()
                project._compute_mortality_rate()
                _logger.info(f"Projet {project.name} mis à jour : {self.scrap_qty} poussins morts ajoutés.")
        return res