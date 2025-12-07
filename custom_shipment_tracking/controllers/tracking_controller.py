# -*- coding: utf-8 -*-
"""
Public tracking page controller.
Allows clients to view parcel status without authentication.
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
        Public tracking page for a parcel.

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

        # Get parcel and related data
        parcel = link.parcel_id
        shipment = parcel.shipment_request_id

        # Get public tracking events, ordered by date desc
        events = request.env['shipment.tracking.event'].sudo().search([
            ('parcel_id', '=', parcel.id),
            ('is_public', '=', True),
        ], order='event_date desc')

        values = {
            'parcel': parcel,
            'shipment': shipment,
            'link': link,
            'events': events,
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
