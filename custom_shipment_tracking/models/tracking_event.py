# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShipmentTrackingEvent(models.Model):
    """Événements de suivi - historique des changements de statut d'un colis."""

    _name = 'shipment.tracking.event'
    _description = 'Événement de suivi'
    _order = 'event_date desc, id desc'
    _rec_name = 'event_type'

    # region Fields
    parcel_id = fields.Many2one(
        comodel_name='shipment.parcel',
        string='Colis',
        required=True,
        ondelete='cascade',
        index=True,
    )
    event_date = fields.Datetime(
        string='Date de l\'événement',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    event_type = fields.Selection(
        selection=[
            ('registered', 'Enregistrement'),
            ('grouping', 'Mise en groupage'),
            ('in_transit', 'Départ en transit'),
            ('arrived', 'Arrivée à destination'),
            ('delivered', 'Livraison'),
            ('note', 'Note'),
            ('exception', 'Exception'),
        ],
        string='Type d\'événement',
        required=True,
        index=True,
    )
    location = fields.Char(
        string='Lieu',
        help='Lieu où l\'événement s\'est produit (ville, entrepôt, etc.)',
    )
    description = fields.Text(
        string='Description',
        help='Détails supplémentaires sur l\'événement',
    )
    is_public = fields.Boolean(
        string='Visible publiquement',
        default=True,
        help='Si coché, cet événement sera visible sur la page de tracking publique',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Utilisateur',
        default=lambda self: self.env.user,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        related='parcel_id.company_id',
        store=True,
        readonly=True,
    )

    # Related parcel info
    parcel_name = fields.Char(
        related='parcel_id.name',
        string='Référence colis',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='parcel_id.partner_id',
        string='Client',
        store=True,
        readonly=True,
    )
    # endregion

    # region Model Methods
    @api.model
    def create_status_event(self, parcel, new_state, location=None, description=None):
        """Create a tracking event for a status change.

        Args:
            parcel: shipment.parcel recordset
            new_state: str, the new state value
            location: str, optional location
            description: str, optional description

        Returns:
            Created shipment.tracking.event record
        """
        vals = {
            'parcel_id': parcel.id,
            'event_type': new_state,
            'location': location,
            'description': description or self._get_default_description(new_state),
            'is_public': True,
        }
        return self.create(vals)

    def _get_default_description(self, event_type):
        """Return default description for event type."""
        descriptions = {
            'registered': 'Colis enregistré dans le système',
            'grouping': 'Colis en cours de groupage pour expédition',
            'in_transit': 'Colis en transit vers la destination',
            'arrived': 'Colis arrivé à destination, en attente de livraison',
            'delivered': 'Colis livré au destinataire',
        }
        return descriptions.get(event_type, '')
    # endregion
