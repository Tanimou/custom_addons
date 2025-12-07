# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShipmentRequest(models.Model):
    """Demande d'expédition - Shipment Request for air and sea transport."""

    _name = 'shipment.request'
    _description = 'Demande d\'expédition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # region Fields
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default='Nouveau',
        tracking=True,
    )
    sale_order_ids = fields.Many2many(
        comodel_name='sale.order',
        relation='shipment_request_sale_order_rel',
        column1='shipment_request_id',
        column2='sale_order_id',
        string='Commandes liées',
        help='Commandes client confirmées liées à cette expédition',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        required=True,
        tracking=True,
        index=True,
    )
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string='Adresse de livraison',
        help='Adresse de destination pour la livraison',
    )
    destination_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Pays de destination',
        required=True,
        tracking=True,
    )
    destination_city = fields.Char(
        string='Ville de destination',
    )
    transport_mode = fields.Selection(
        selection=[
            ('air', 'Aérien'),
            ('sea', 'Maritime'),
        ],
        string='Mode de transport',
        required=True,
        default='air',
        tracking=True,
    )
    planned_date = fields.Date(
        string='Date prévue d\'expédition',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('registered', 'Enregistré'),
            ('grouping', 'Groupage'),
            ('in_transit', 'En transit'),
            ('arrived', 'Arrivé à destination'),
            ('delivered', 'Livré'),
        ],
        string='Statut',
        default='registered',
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    parcel_ids = fields.One2many(
        comodel_name='shipment.parcel',
        inverse_name='shipment_request_id',
        string='Colis',
    )
    parcel_count = fields.Integer(
        string='Nombre de colis',
        compute='_compute_parcel_count',
        store=True,
    )
    tracking_link_id = fields.Many2one(
        comodel_name='shipment.tracking.link',
        string='Lien de suivi',
        readonly=True,
        copy=False,
        compute='_compute_tracking_link_id',
        store=True,
    )
    main_parcel_number = fields.Char(
        string='Numéro principal',
        copy=False,
        readonly=True,
        help='Numéro de colis principal au format ABXXXX',
    )
    notes = fields.Text(
        string='Notes internes',
    )

    # Air transport specific fields
    air_flight_number = fields.Char(
        string='Numéro de vol',
    )
    air_departure_airport = fields.Char(
        string='Aéroport de départ',
    )
    air_arrival_airport = fields.Char(
        string='Aéroport d\'arrivée',
    )
    air_departure_datetime = fields.Datetime(
        string='Date/heure de départ',
    )

    # Sea transport specific fields
    sea_vessel_name = fields.Char(
        string='Nom du navire',
    )
    sea_departure_port = fields.Char(
        string='Port de départ',
    )
    sea_arrival_port = fields.Char(
        string='Port d\'arrivée',
    )
    sea_embarkation_date = fields.Date(
        string='Date d\'embarquement',
    )
    sea_container_number = fields.Char(
        string='Numéro de conteneur',
    )

    # Computed/Related fields
    tracking_url = fields.Char(
        string='URL de suivi',
        related='tracking_link_id.url',
        readonly=True,
    )
    # endregion

    # region Computes
    @api.depends('parcel_ids')
    def _compute_parcel_count(self):
        for record in self:
            record.parcel_count = len(record.parcel_ids)

    @api.depends('parcel_ids.tracking_link_ids')
    def _compute_tracking_link_id(self):
        """Get the first active tracking link from parcels."""
        for record in self:
            link = self.env['shipment.tracking.link'].search([
                ('parcel_id', 'in', record.parcel_ids.ids),
                ('is_active', '=', True),
            ], limit=1)
            record.tracking_link_id = link.id if link else False
    # endregion

    # region CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('shipment.request') or 'Nouveau'
        return super().create(vals_list)
    # endregion

    # region Business Methods
    def _get_or_create_main_parcel_number(self):
        """
        Returns the main parcel number (ABXXXX) for this shipment request.
        If not yet assigned, generates a new one using ir.sequence.
        """
        self.ensure_one()
        if not self.main_parcel_number:
            self.main_parcel_number = self.env['ir.sequence'].next_by_code(
                'shipment.parcel.main.number'
            )
            _logger.info(
                'Generated main parcel number %s for shipment request %s',
                self.main_parcel_number,
                self.name,
            )
        return self.main_parcel_number

    def action_set_grouping(self):
        """Set status to Groupage."""
        self.write({'state': 'grouping'})

    def action_set_in_transit(self):
        """Set status to En transit."""
        self.write({'state': 'in_transit'})

    def action_set_arrived(self):
        """Set status to Arrivé à destination."""
        self.write({'state': 'arrived'})

    def action_set_delivered(self):
        """Set status to Livré."""
        self.write({'state': 'delivered'})

    def action_generate_tracking_link(self):
        """Generate tracking links for all parcels of this shipment."""
        self.ensure_one()
        if not self.parcel_ids:
            from odoo.exceptions import UserError
            raise UserError('Aucun colis associé à cette expédition. Créez d\'abord des colis.')

        TrackingLink = self.env['shipment.tracking.link']
        created_links = self.env['shipment.tracking.link']

        for parcel in self.parcel_ids:
            # Check if parcel already has an active tracking link
            existing = TrackingLink.search([
                ('parcel_id', '=', parcel.id),
                ('is_active', '=', True),
            ], limit=1)
            if not existing:
                link = TrackingLink.create({'parcel_id': parcel.id})
                created_links |= link
                _logger.info(
                    'Generated tracking link %s for parcel %s',
                    link.token,
                    parcel.name,
                )

        if created_links:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'shipment.tracking.link',
                'view_mode': 'list,form',
                'domain': [('id', 'in', created_links.ids)],
                'name': 'Liens de suivi générés',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Tous les colis ont déjà un lien de suivi actif.',
                    'type': 'info',
                    'sticky': False,
                }
            }
    # endregion


class SaleOrderShipmentExtension(models.Model):
    """Extension to sale.order to support automatic shipment request creation."""

    _inherit = 'sale.order'

    shipment_request_ids = fields.Many2many(
        comodel_name='shipment.request',
        relation='shipment_request_sale_order_rel',
        column1='sale_order_id',
        column2='shipment_request_id',
        string='Demandes d\'expédition',
    )
    shipment_request_count = fields.Integer(
        string='Nombre d\'expéditions',
        compute='_compute_shipment_request_count',
    )

    @api.depends('shipment_request_ids')
    def _compute_shipment_request_count(self):
        for order in self:
            order.shipment_request_count = len(order.shipment_request_ids)

    def action_confirm(self):
        """Override to create shipment request on CRM-originated order confirmation."""
        res = super().action_confirm()
        for order in self:
            # Check if order originates from CRM (has opportunity_id)
            if order.opportunity_id and not order.shipment_request_ids:
                order._create_shipment_request_from_order()
        return res

    def _create_shipment_request_from_order(self):
        """Create a shipment request linked to this confirmed order."""
        self.ensure_one()
        ShipmentRequest = self.env['shipment.request']

        vals = {
            'sale_order_ids': [(4, self.id)],
            'partner_id': self.partner_id.id,
            'partner_shipping_id': self.partner_shipping_id.id if self.partner_shipping_id else False,
            'destination_country_id': (
                self.partner_shipping_id.country_id.id
                if self.partner_shipping_id and self.partner_shipping_id.country_id
                else self.partner_id.country_id.id
                if self.partner_id.country_id
                else False
            ),
            'destination_city': (
                self.partner_shipping_id.city
                if self.partner_shipping_id
                else self.partner_id.city
            ),
            'company_id': self.company_id.id,
        }

        # Validate required fields
        if not vals.get('destination_country_id'):
            _logger.warning(
                'Cannot auto-create shipment request for order %s: missing destination country',
                self.name,
            )
            return False

        shipment = ShipmentRequest.create(vals)
        _logger.info(
            'Auto-created shipment request %s from order %s',
            shipment.name,
            self.name,
        )
        return shipment

    def action_view_shipment_requests(self):
        """Open shipment requests linked to this order."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'custom_shipment_tracking.action_shipment_request'
        )
        if self.shipment_request_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.shipment_request_ids.id
        else:
            action['domain'] = [('id', 'in', self.shipment_request_ids.ids)]
        return action
