# -*- coding: utf-8 -*-

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShipmentTrackingLink(models.Model):
    """Lien de suivi public pour clients - un lien unique par colis."""

    _name = 'shipment.tracking.link'
    _description = 'Lien de suivi'
    _order = 'create_date desc'
    _rec_name = 'token'

    # region Fields
    parcel_id = fields.Many2one(
        comodel_name='shipment.parcel',
        string='Colis',
        required=True,
        ondelete='cascade',
        index=True,
    )
    token = fields.Char(
        string='Token',
        required=True,
        index=True,
        readonly=True,
        default=lambda self: str(uuid.uuid4()),
    )
    url = fields.Char(
        string='URL de suivi',
        compute='_compute_url',
        store=False,
    )
    is_active = fields.Boolean(
        string='Actif',
        default=True,
    )
    access_count = fields.Integer(
        string='Nombre d\'accès',
        default=0,
        readonly=True,
    )
    last_access = fields.Datetime(
        string='Dernier accès',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        related='parcel_id.company_id',
        store=True,
        readonly=True,
    )

    # Related parcel info for display
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
    parcel_state = fields.Selection(
        related='parcel_id.state',
        string='Statut colis',
        readonly=True,
    )
    # endregion

    # region Constraints
    _sql_constraints = [
        (
            'unique_token',
            'UNIQUE(token)',
            'Le token de tracking doit être unique.',
        ),
        (
            'unique_parcel_active',
            'EXCLUDE (parcel_id WITH =) WHERE (is_active = true)',
            'Un seul lien actif est autorisé par colis.',
        ),
    ]
    # endregion

    # region Computes
    @api.depends('token')
    def _compute_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for link in self:
            if link.token:
                link.url = f'{base_url}/tracking/{link.token}'
            else:
                link.url = False
    # endregion

    # region Business Methods
    def action_deactivate(self):
        """Deactivate tracking link."""
        self.write({'is_active': False})

    def action_regenerate_token(self):
        """Generate a new token for the link."""
        for link in self:
            link.token = str(uuid.uuid4())
        return True

    def record_access(self):
        """Record an access to the tracking page."""
        self.sudo().write({
            'access_count': self.access_count + 1,
            'last_access': fields.Datetime.now(),
        })
    # endregion
