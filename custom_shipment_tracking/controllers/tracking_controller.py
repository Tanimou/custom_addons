# -*- coding: utf-8 -*-
"""
Public tracking page controller.
Allows clients to view their shipment parcels status without authentication.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TrackingController(http.Controller):
    """Controller for public tracking page."""

    @http.route(
        '/tracking/<string:token>',
        type='http',
        auth='public',
        website=True,
        sitemap=False,
    )
    def tracking_page(self, token, **kwargs):
        """
        Public tracking page for a shipment's parcels.

        Args:
            token: The tracking link token (UUID)

        Returns:
            Rendered tracking page template or 404
        """
        TrackingLink = request.env['shipment.tracking.link'].sudo()

        # Find active tracking link
        link = TrackingLink.search([
            ('token', '=', token),
            ('is_active', '=', True),
        ], limit=1)

        if not link:
            _logger.warning('Tracking link not found or inactive: %s', token)
            return request.render(
                'custom_shipment_tracking.tracking_page_not_found',
                {'token': token},
            )

        # Record access
        link.record_access()

        # Get shipment and its parcels
        shipment = link.shipment_request_id
        partner = shipment.partner_id
        parcels = link.get_shipment_parcels()

        # Get events for all parcels in this shipment
        events = request.env['shipment.tracking.event'].sudo().search([
            ('parcel_id', 'in', parcels.ids),
            ('is_public', '=', True),
        ], order='event_date desc', limit=10)

        shipment_data = {
            'shipment': shipment,
            'parcels': parcels,
            'events': events,
        }

        # Calculate overall stats
        total_parcels = len(parcels)
        delivered_count = len(parcels.filtered(lambda p: p.state == 'delivered'))
        in_transit_count = len(parcels.filtered(lambda p: p.state == 'in_transit'))
        arrived_count = len(parcels.filtered(lambda p: p.state == 'arrived'))

        values = {
            'partner': partner,
            'link': link,
            'shipment_data': shipment_data,
            'total_parcels': total_parcels,
            'delivered_count': delivered_count,
            'in_transit_count': in_transit_count,
            'arrived_count': arrived_count,
            'status_labels': {
                'registered': 'Enregistré',
                'grouping': 'En groupage',
                'in_transit': 'En transit',
                'arrived': 'Arrivé à destination',
                'delivered': 'Livré',
            },
            'status_icons': {
                'registered': 'fa-check-circle',
                'grouping': 'fa-boxes',
                'in_transit': 'fa-truck',
                'arrived': 'fa-map-marker',
                'delivered': 'fa-home',
            },
            'status_colors': {
                'registered': 'info',
                'grouping': 'warning',
                'in_transit': 'primary',
                'arrived': 'success',
                'delivered': 'success',
            },
        }

        return request.render(
            'custom_shipment_tracking.tracking_page',
            values,
        )
