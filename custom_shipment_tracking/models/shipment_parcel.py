# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShipmentParcel(models.Model):
    """Colis - Physical parcel belonging to a shipment request."""

    _name = 'shipment.parcel'
    _description = 'Colis'
    _order = 'shipment_request_id, sequence, id'

    # region Fields
    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande d\'expédition',
        required=True,
        ondelete='cascade',
        index=True,
    )
    main_number = fields.Char(
        string='Numéro principal',
        readonly=True,
        help='Numéro de colis principal au format ABXXXX',
    )
    sequence = fields.Integer(
        string='N° sous-référence',
        default=1,
        readonly=True,
    )
    weight = fields.Float(
        string='Poids (kg)',
        required=True,
        default=0.0,
    )
    length = fields.Float(
        string='Longueur (cm)',
        default=0.0,
    )
    width = fields.Float(
        string='Largeur (cm)',
        default=0.0,
    )
    height = fields.Float(
        string='Hauteur (cm)',
        default=0.0,
    )
    content_description = fields.Char(
        string='Nature du contenu',
        help='Ex: vêtements, documents, denrées alimentaires',
    )
    declared_value = fields.Monetary(
        string='Valeur déclarée',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    transport_mode = fields.Selection(
        selection=[
            ('air', 'Aérien'),
            ('sea', 'Maritime'),
        ],
        string='Mode de transport',
        help='Laissez vide pour hériter de la demande d\'expédition',
    )
    destination_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Pays de destination',
        help='Laissez vide pour hériter de la demande d\'expédition',
    )
    destination_city = fields.Char(
        string='Ville de destination',
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
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        related='shipment_request_id.company_id',
        store=True,
        readonly=True,
    )

    # Related fields for display
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        related='shipment_request_id.partner_id',
        store=True,
        readonly=True,
    )
    tracking_link_ids = fields.One2many(
        comodel_name='shipment.tracking.link',
        inverse_name='parcel_id',
        string='Liens de suivi',
    )
    tracking_event_ids = fields.One2many(
        comodel_name='shipment.tracking.event',
        inverse_name='parcel_id',
        string='Événements de suivi',
    )
    parcel_line_ids = fields.One2many(
        comodel_name='shipment.parcel.line',
        inverse_name='parcel_id',
        string='Produits du colis',
    )
    product_count = fields.Integer(
        string='Nombre de produits',
        compute='_compute_product_info',
        store=True,
    )
    product_summary = fields.Char(
        string='Contenu',
        compute='_compute_product_info',
        store=True,
        help='Résumé des produits contenus dans ce colis',
    )
    total_value = fields.Monetary(
        string='Valeur totale',
        compute='_compute_product_info',
        store=True,
        currency_field='currency_id',
    )
    shipment_transport_mode = fields.Selection(
        related='shipment_request_id.transport_mode',
        string='Mode transport (expédition)',
        readonly=True,
    )
    shipment_destination_country_id = fields.Many2one(
        related='shipment_request_id.destination_country_id',
        string='Pays destination (expédition)',
        readonly=True,
    )

    # Computed effective values
    effective_transport_mode = fields.Selection(
        selection=[
            ('air', 'Aérien'),
            ('sea', 'Maritime'),
        ],
        string='Mode de transport effectif',
        compute='_compute_effective_values',
        store=True,
    )
    effective_destination_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Pays de destination effectif',
        compute='_compute_effective_values',
        store=True,
    )
    # endregion

    # region Constraints
    @api.constrains('weight')
    def _check_weight(self):
        for parcel in self:
            if parcel.weight <= 0:
                raise ValidationError(
                    'Le poids du colis doit être supérieur à zéro.'
                )

    _sql_constraints = [
        (
            'unique_main_sequence',
            'UNIQUE(main_number, sequence)',
            'La combinaison numéro principal / sous-référence doit être unique.',
        ),
    ]
    # endregion

    # region Computes
    @api.depends('main_number', 'sequence')
    def _compute_name(self):
        for parcel in self:
            if parcel.main_number:
                parcel.name = f'{parcel.main_number}-{parcel.sequence}'
            else:
                parcel.name = 'Nouveau'

    @api.depends('transport_mode', 'destination_country_id', 'shipment_request_id.transport_mode', 'shipment_request_id.destination_country_id')
    def _compute_effective_values(self):
        for parcel in self:
            parcel.effective_transport_mode = (
                parcel.transport_mode
                or parcel.shipment_request_id.transport_mode
            )
            parcel.effective_destination_country_id = (
                parcel.destination_country_id
                or parcel.shipment_request_id.destination_country_id
            )

    @api.depends('parcel_line_ids', 'parcel_line_ids.product_id', 'parcel_line_ids.quantity', 'parcel_line_ids.subtotal')
    def _compute_product_info(self):
        """Compute product count, summary, and total value from parcel lines."""
        for parcel in self:
            lines = parcel.parcel_line_ids
            parcel.product_count = len(lines)
            if lines:
                product_names = lines.mapped('product_id.name')
                parcel.product_summary = ', '.join(filter(None, product_names[:3]))
                if len(product_names) > 3:
                    parcel.product_summary += f' (+{len(product_names) - 3})'
                parcel.total_value = sum(lines.mapped('subtotal'))
            else:
                parcel.product_summary = ''
                parcel.total_value = 0.0
    # endregion

    # region Onchange
    @api.onchange('length', 'width', 'height')
    def _onchange_dimensions(self):
        """Warn if all dimensions are zero."""
        if self.length == 0 and self.width == 0 and self.height == 0:
            return {
                'warning': {
                    'title': 'Dimensions non renseignées',
                    'message': 'Les dimensions du colis (longueur, largeur, hauteur) ne sont pas renseignées.',
                }
            }
    # endregion

    # region CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            shipment_request_id = vals.get('shipment_request_id')
            if shipment_request_id:
                shipment = self.env['shipment.request'].browse(shipment_request_id)
                # Get or create main parcel number
                main_number = shipment._get_or_create_main_parcel_number()
                vals['main_number'] = main_number
                # Assign next sequence
                existing_parcels = self.search([
                    ('shipment_request_id', '=', shipment_request_id),
                ], order='sequence desc', limit=1)
                next_sequence = (existing_parcels.sequence + 1) if existing_parcels else 1
                vals['sequence'] = next_sequence
                _logger.info(
                    'Creating parcel %s-%d for shipment %s',
                    main_number,
                    next_sequence,
                    shipment.name,
                )
        return super().create(vals_list)
    # endregion

    # region Business Methods
    def action_set_state(self, new_state):
        """Set state for selected parcels."""
        self.write({'state': new_state})

    def action_set_grouping(self):
        self.action_set_state('grouping')

    def action_set_in_transit(self):
        self.action_set_state('in_transit')

    def action_set_arrived(self):
        self.action_set_state('arrived')

    def action_set_delivered(self):
        self.action_set_state('delivered')

    def action_generate_tracking_link(self):
        """Generate a tracking link for this parcel."""
        self.ensure_one()
        TrackingLink = self.env['shipment.tracking.link']

        # Check for existing active link
        existing = TrackingLink.search([
            ('parcel_id', '=', self.id),
            ('is_active', '=', True),
        ], limit=1)

        if existing:
            link = existing
        else:
            link = TrackingLink.create({'parcel_id': self.id})
            _logger.info('Generated tracking link %s for parcel %s', link.token, self.name)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.tracking.link',
            'res_id': link.id,
            'view_mode': 'form',
            'target': 'new',
            'name': 'Lien de suivi',
        }

    def action_view_tracking_events(self):
        """View tracking events for this parcel."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.tracking.event',
            'view_mode': 'list,form',
            'domain': [('parcel_id', '=', self.id)],
            'context': {'default_parcel_id': self.id},
            'name': f'Événements - {self.name}',
        }

    def action_open_product_wizard(self):
        """Open wizard to add/view products in parcel.
        
        When shipment is in 'registered' state, allows editing.
        In other states, opens in read-only mode.
        """
        self.ensure_one()
        shipment_state = self.shipment_request_id.state
        is_readonly = shipment_state != 'registered'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'parcel.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': f'Produits du colis {self.name}',
            'context': {
                'default_parcel_id': self.id,
                'default_shipment_request_id': self.shipment_request_id.id,
                'readonly_mode': is_readonly,
            },
        }
    # endregion
