from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time
import re
import logging

_logger = logging.getLogger(__name__)


class OfficeRoomBooking(models.Model):
    _name = 'office.room.booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'


    name = fields.Char(
        string='Nom du bureau',
        required=True,
    )
    equipment_ids = fields.Many2many(
        comodel_name='product.template',
        string='Equipements',
    )
    description = fields.Char(
        string='Description',
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Occupant',
        required=True,
    )
    building_id = fields.Many2one(
        'building.room.booking',
        string='Batiment',
        required=True,
    )


class BuildingRoomBooking(models.Model):
    _name = 'building.room.booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'


    name = fields.Char(
        string='Nom du batiment',
        required=True,
    )
    description = fields.Text(
        string='Description',
    )