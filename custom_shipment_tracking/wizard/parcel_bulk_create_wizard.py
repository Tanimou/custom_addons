# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ParcelBulkCreateWizard(models.TransientModel):
    """Wizard to bulk create parcels for a shipment request."""

    _name = 'parcel.bulk.create.wizard'
    _description = 'Creation de colis en masse'

    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande d\'expedition',
        required=True,
        readonly=True,
    )
    parcel_count = fields.Integer(
        string='Nombre de colis',
        default=1,
        required=True,
        help='Nombre de colis a creer',
    )
    default_weight = fields.Float(
        string='Poids par defaut (kg)',
        default=1.0,
        required=True,
        help='Poids applique a chaque colis cree',
    )
    default_declared_value = fields.Monetary(
        string='Valeur declaree par defaut',
        currency_field='currency_id',
        help='Valeur declaree appliquee a chaque colis (optionnel)',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
    )
    content_description = fields.Char(
        string='Nature du contenu',
        help='Description du contenu appliquee a tous les colis',
    )

    # Computed info fields
    main_number_preview = fields.Char(
        string='Numero principal',
        compute='_compute_preview',
    )
    first_sequence_preview = fields.Integer(
        string='Premiere sequence',
        compute='_compute_preview',
    )
    last_sequence_preview = fields.Integer(
        string='Derniere sequence',
        compute='_compute_preview',
    )
    total_weight_preview = fields.Float(
        string='Poids total',
        compute='_compute_preview',
    )

    @api.constrains('parcel_count')
    def _check_parcel_count(self):
        for wizard in self:
            if wizard.parcel_count < 1:
                raise ValidationError('Le nombre de colis doit etre au moins 1.')
            if wizard.parcel_count > 500:
                raise ValidationError('Le nombre maximum de colis par creation est 500.')

    @api.constrains('default_weight')
    def _check_default_weight(self):
        for wizard in self:
            if wizard.default_weight <= 0:
                raise ValidationError('Le poids doit etre superieur a zero.')

    @api.depends('shipment_request_id', 'parcel_count', 'default_weight')
    def _compute_preview(self):
        for wizard in self:
            if not wizard.shipment_request_id:
                wizard.main_number_preview = ''
                wizard.first_sequence_preview = 0
                wizard.last_sequence_preview = 0
                wizard.total_weight_preview = 0.0
                continue

            shipment = wizard.shipment_request_id
            main_number = shipment._get_or_create_main_parcel_number()
            wizard.main_number_preview = main_number

            # Get current max sequence
            existing_parcels = self.env['shipment.parcel'].search([
                ('shipment_request_id', '=', shipment.id),
            ], order='sequence desc', limit=1)
            first_sequence = (existing_parcels.sequence + 1) if existing_parcels else 1

            wizard.first_sequence_preview = first_sequence
            wizard.last_sequence_preview = first_sequence + wizard.parcel_count - 1
            wizard.total_weight_preview = wizard.parcel_count * wizard.default_weight

    def action_create_parcels(self):
        """Create multiple parcels at once."""
        self.ensure_one()

        if not self.shipment_request_id:
            raise UserError('Aucune demande d\'expedition selectionnee.')

        shipment = self.shipment_request_id

        # Verify shipment state allows parcel creation
        if shipment.state not in ('registered', 'grouping'):
            raise UserError(
                'Impossible de creer des colis. L\'expedition doit etre en etat '
                '"Enregistre" ou "Groupage".'
            )

        # Prepare vals for bulk creation
        # Parcel state should match shipment state
        parcel_state = shipment.state if shipment.state in ('registered', 'grouping') else 'registered'
        
        vals_list = []
        for _ in range(self.parcel_count):
            vals = {
                'shipment_request_id': shipment.id,
                'weight': self.default_weight,
                'state': parcel_state,
            }
            if self.default_declared_value:
                vals['declared_value'] = self.default_declared_value
            if self.content_description:
                vals['content_description'] = self.content_description
            vals_list.append(vals)

        # Bulk create parcels (create() handles main_number and sequence)
        created_parcels = self.env['shipment.parcel'].create(vals_list)

        _logger.info(
            'Bulk created %d parcels for shipment %s (refs: %s to %s)',
            len(created_parcels),
            shipment.name,
            created_parcels[0].name if created_parcels else 'N/A',
            created_parcels[-1].name if created_parcels else 'N/A',
        )

        # Post message in chatter
        shipment.message_post(
            body=f"<strong>{len(created_parcels)} colis crees en masse</strong><br/>"
                 f"References: {created_parcels[0].name} a {created_parcels[-1].name}<br/>"
                 f"Poids unitaire: {self.default_weight} kg<br/>"
                 f"Poids total: {self.total_weight_preview} kg",
            message_type='notification',
        )

        return {'type': 'ir.actions.act_window_close'}
