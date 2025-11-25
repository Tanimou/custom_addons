from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime, time
import re
import logging

_logger = logging.getLogger(__name__)


class ReservationRoomBooking(models.Model):
    _name = 'reservation.room.booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Nom de la réservation',
        required=True,
    )
    description = fields.Char(
        string='Motif de la reservation',
    )
    organized_id = fields.Many2one(
        'res.users',
        string='Organisateurs',
        required=True,
        default=lambda self: self.env.user
    )
    room_id = fields.Many2one(
        'room.room',
        string='Salle',
        required=True,
    )
    room_booking_id = fields.Many2one(
        'room.booking',
        string='Reservation',
    )
    responsable_id = fields.Many2one(
        'res.users',
        string='Validateur',
        required=True,
    )
    date_from = fields.Datetime(
        string='Date de début',
        required=True,
        default=fields.Date.context_today
    )
    date_to = fields.Datetime(
        string='Date de fin',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ('draft', 'Brouillon'), 
            ('submit', 'Soumettre'), 
            ('done', 'Valider'),
            ('refun', 'Refuser'),
        ], string='État', 
        default='draft', 
        required=True
    )
    room_id_domain = fields.Char(
        compute='_compute_room_id_domain',
        readonly=True,
        store=False
    )

    def action_validate(self):
        for rec in self:
            rec.action_create_reservation()
        self.write({'state': 'done'})

    def action_submit(self):
        self.write({'state': 'submit'})

    def action_refun(self):
        self.write({'state': 'refun'})

    def action_create_reservation(self):
        for rec in self:
            room_create = self.env['room.booking']
            vals = {
                'name': rec.name,
                'room_id': rec.room_id.id,
                'stop_datetime': rec.date_to,
                'start_datetime': rec.date_from,
                'organizer_id': rec.organized_id.id,
            }
            self.room_booking_id = room_create.create(vals)

    
    @api.depends('date_from', 'date_to')
    def _compute_room_id_domain(self):
        for record in self:
            if not record.date_from or not record.date_to:
                record.room_id_domain = [
                    ('under_construction', '=', False),
                    ('active', '=', True)
                ]
            else:
                # Récupérer salles non en construction
                all_rooms = self.env['room.room'].search([
                    ('under_construction', '=', False),
                    ('active', '=', True),
                ])
                
                # Salles réservées
                booked_rooms = self.env['room.booking'].search([
                    ('id', '!=', record.id),
                    ('start_datetime', '<', record.date_to),
                    ('stop_datetime', '>', record.date_from),
                ]).mapped('room_id')
                
                available_rooms = all_rooms - booked_rooms
                record.room_id_domain = [('id', 'in', available_rooms.ids)]
    