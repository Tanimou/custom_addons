# -*- coding: utf-8 -*-

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ShipmentTrackingLink(models.Model):
    """Lien de suivi public - un lien unique par expédition."""

    _name = 'shipment.tracking.link'
    _description = 'Lien de suivi'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # region Fields
    # Primary link to shipment (NEW - per shipment architecture)
    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Expédition',
        required=True,
        ondelete='cascade',
        index=True,
    )
    # Partner is derived from shipment for convenience
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        related='shipment_request_id.partner_id',
        store=True,
        readonly=True,
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
        related='shipment_request_id.company_id',
        store=True,
        readonly=True,
    )

    # Computed counts for display
    parcel_count = fields.Integer(
        string='Nombre de colis',
        compute='_compute_parcel_count',
        store=False,
    )
    display_name = fields.Char(
        string='Nom',
        compute='_compute_display_name',
        store=True,
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
            'unique_shipment_active',
            'EXCLUDE (shipment_request_id WITH =) WHERE (is_active = true)',
            'Un seul lien actif est autorisé par expédition.',
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

    @api.depends('shipment_request_id', 'shipment_request_id.name')
    def _compute_display_name(self):
        for link in self:
            if link.shipment_request_id:
                link.display_name = f"Suivi - {link.shipment_request_id.name}"
            else:
                link.display_name = link.token or 'Nouveau lien'

    def _compute_parcel_count(self):
        """Compute the number of parcels for this shipment."""
        for link in self:
            if link.shipment_request_id:
                link.parcel_count = len(link.shipment_request_id.parcel_ids)
            else:
                link.parcel_count = 0
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

    def get_shipment_parcels(self):
        """Get all parcels for this shipment."""
        self.ensure_one()
        if not self.shipment_request_id:
            return self.env['shipment.parcel']
        return self.shipment_request_id.parcel_ids.sorted(key=lambda p: p.sequence)

    def action_view_parcels(self):
        """View all parcels for this shipment."""
        self.ensure_one()
        parcels = self.get_shipment_parcels()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Colis - {self.shipment_request_id.name}',
            'res_model': 'shipment.parcel',
            'view_mode': 'list,form',
            'domain': [('id', 'in', parcels.ids)],
            'target': 'current',
        }
    # endregion
