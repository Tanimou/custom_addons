from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time
import re
import logging

_logger = logging.getLogger(__name__)


class RoomRoomInherit(models.Model):
    _inherit = 'room.room'

    num_place = fields.Integer(
        string='Nombre de places',
        required=True,
    )
    equipment_ids = fields.Many2many(
        comodel_name='product.template',
        string='Equipements',
    )
    under_construction = fields.Boolean(
        string="Chambre en travaux", 
        default=False)
    

    def compute_under_construction(self):
        self.under_construction = True

    def compute_not_under_construction(self):
        self.under_construction = False

    def action_generate_index_html(self):
        """Vide et génère la liste HTML"""
        for record in self:
            # Vider le champ
            record.description = ''
            html_content = '<ol>'
            if record.num_place:
                html_content += f'<li>{record.num_place}</li>'
            if record.equipment_ids:
                for equipment in record.equipment_ids:
                    html_content += f'<li>{equipment.name}</li>'
                html_content += '</ol>'
                record.description = html_content
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Mise ajours des equipements avec succès!',
                'type': 'success',
                'sticky': False,
            }
        }