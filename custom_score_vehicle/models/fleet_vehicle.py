# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
T021-T022, T024, T028, T030, T032: Fleet Vehicle extensions for SCORE
- FR-002: Minimum required fields (provenance)
- FR-003: Internal identifier (vehicle_code) - already in custom_fleet_management
- FR-004: Conditional uniqueness (VIN + plate if set)
- FR-010: Driver/team KPIs helper methods
- FR-011: Operational status history (_get_state_history)
- Registration case One2many
- Transfer tracking (current_location_id)
"""

import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FleetVehicleScore(models.Model):
    """SCORE extensions for fleet.vehicle."""
    
    _inherit = 'fleet.vehicle'

    # ==========================================================================
    # FR-002: Minimum Required Fields - Delta (provenance)
    # ==========================================================================
    
    provenance = fields.Selection(
        [
            ('new_purchase', 'Achat neuf'),
            ('used_purchase', 'Achat occasion'),
            ('lease', 'Location'),
            ('transfer', 'Transfert inter-société'),
            ('donation', 'Don'),
            ('other', 'Autre'),
        ],
        string='Provenance',
        tracking=True,
        help="Origine d'acquisition du véhicule/engin"
    )
    
    # ==========================================================================
    # Registration Cases (FR-008) - One2many link
    # ==========================================================================
    
    registration_case_ids = fields.One2many(
        'fleet.vehicle.registration.case',
        'vehicle_id',
        string='Dossiers Immatriculation',
        help="Historique des dossiers d'immatriculation pour ce véhicule"
    )
    
    registration_case_count = fields.Integer(
        string='Nb Dossiers',
        compute='_compute_registration_case_count',
        help="Nombre de dossiers d'immatriculation"
    )
    
    # ==========================================================================
    # Transfers (FR-016) - One2many link + current location
    # ==========================================================================
    
    transfer_ids = fields.One2many(
        'fleet.vehicle.transfer',
        'vehicle_id',
        string='Transferts',
        help="Historique des transferts de ce véhicule"
    )
    
    transfer_count = fields.Integer(
        string='Nb Transferts',
        compute='_compute_transfer_count',
        help="Nombre de transferts effectués"
    )
    
    current_location_id = fields.Many2one(
        'stock.location',
        string='Emplacement Actuel',
        tracking=True,
        domain="[('usage', '=', 'internal')]",
        help="Emplacement actuel du véhicule/engin"
    )
    
    # ==========================================================================
    # Compute Methods
    # ==========================================================================
    
    @api.depends('registration_case_ids')
    def _compute_registration_case_count(self):
        for vehicle in self:
            vehicle.registration_case_count = len(vehicle.registration_case_ids)
    
    @api.depends('transfer_ids')
    def _compute_transfer_count(self):
        for vehicle in self:
            vehicle.transfer_count = len(vehicle.transfer_ids)
    
    # ==========================================================================
    # FR-004: Conditional Uniqueness Constraints
    # ==========================================================================
    
    @api.constrains('vin_sn')
    def _check_vin_unique_if_set(self):
        """VIN must be unique if provided (non-empty)."""
        for vehicle in self:
            if vehicle.vin_sn:
                duplicates = self.search([
                    ('vin_sn', '=', vehicle.vin_sn),
                    ('id', '!=', vehicle.id),
                ], limit=1)
                if duplicates:
                    raise ValidationError(_(
                        "Le numéro de châssis (VIN) '%s' est déjà utilisé par le véhicule %s. "
                        "Le VIN doit être unique s'il est renseigné.",
                        vehicle.vin_sn, duplicates.display_name
                    ))
    
    @api.constrains('license_plate')
    def _check_license_plate_unique_if_set(self):
        """License plate must be unique if provided (non-empty)."""
        for vehicle in self:
            if vehicle.license_plate:
                duplicates = self.search([
                    ('license_plate', '=', vehicle.license_plate),
                    ('id', '!=', vehicle.id),
                ], limit=1)
                if duplicates:
                    raise ValidationError(_(
                        "L'immatriculation '%s' est déjà utilisée par le véhicule %s. "
                        "L'immatriculation doit être unique si elle est renseignée.",
                        vehicle.license_plate, duplicates.display_name
                    ))
    
    # ==========================================================================
    # FR-011: Operational Status History
    # ==========================================================================
    
    def _get_state_history(self):
        """
        Returns the history of state_id changes for this vehicle.
        Uses mail.tracking.value from the chatter system.
        
        :return: recordset of mail.tracking.value ordered by create_date desc
        """
        self.ensure_one()
        TrackingValue = self.env['mail.tracking.value']
        field = self.env['ir.model.fields']._get('fleet.vehicle', 'state_id')
        
        if not field:
            return TrackingValue.browse()
        
        return TrackingValue.search([
            ('field_id', '=', field.id),
            ('mail_message_id.model', '=', 'fleet.vehicle'),
            ('mail_message_id.res_id', '=', self.id),
        ], order='create_date desc')
    
    # ==========================================================================
    # FR-010: Driver/Team KPI Helper Methods
    # ==========================================================================
    
    def _get_driver_missions_domain(self, driver, date_from=None, date_to=None, 
                                     state_filter=None, exclude_zero_km=False):
        """
        Build domain for driver missions filtering.
        
        :param driver: res.partner recordset (driver)
        :param date_from: optional datetime/date for period start
        :param date_to: optional datetime/date for period end
        :param state_filter: list of states to include (default: ['done'])
        :param exclude_zero_km: if True, exclude missions with distance_km <= 0
        :return: domain list
        """
        if state_filter is None:
            state_filter = ['done']
        
        domain = [
            ('vehicle_id', '=', self.id),
            ('driver_id', '=', driver.id),
            ('state', 'in', state_filter),
        ]
        
        if date_from:
            domain.append(('date_start', '>=', date_from))
        
        if date_to:
            domain.append(('date_start', '<=', date_to))
        
        if exclude_zero_km:
            domain.append(('distance_km', '>', 0))
        
        return domain
    
    def _get_driver_mission_count(self, driver, date_from=None, date_to=None):
        """
        Count completed missions for a driver on this vehicle.
        Excludes cancelled missions.
        
        :param driver: res.partner recordset
        :param date_from: optional period start
        :param date_to: optional period end
        :return: integer count
        """
        self.ensure_one()
        Mission = self.env['fleet.mission']
        domain = self._get_driver_missions_domain(driver, date_from, date_to)
        return Mission.search_count(domain)
    
    def _get_driver_total_km(self, driver, date_from=None, date_to=None):
        """
        Sum of distance_km for completed missions for a driver.
        Excludes cancelled missions and missions with 0 km.
        
        :param driver: res.partner recordset
        :param date_from: optional period start
        :param date_to: optional period end
        :return: float total km
        """
        self.ensure_one()
        Mission = self.env['fleet.mission']
        domain = self._get_driver_missions_domain(
            driver, date_from, date_to, exclude_zero_km=True
        )
        missions = Mission.search(domain)
        return sum(missions.mapped('distance_km'))
    
    def _get_driver_total_days(self, driver, date_from=None, date_to=None):
        """
        Sum of duration_days for completed missions for a driver.
        Excludes cancelled missions.
        
        :param driver: res.partner recordset
        :param date_from: optional period start
        :param date_to: optional period end
        :return: float total days
        """
        self.ensure_one()
        Mission = self.env['fleet.mission']
        domain = self._get_driver_missions_domain(driver, date_from, date_to)
        missions = Mission.search(domain)
        return sum(missions.mapped('duration_days'))
    
    def _get_driver_avg_km(self, driver, date_from=None, date_to=None):
        """
        Average km per mission for a driver.
        Excludes cancelled missions and missions with 0 km.
        
        :param driver: res.partner recordset
        :param date_from: optional period start
        :param date_to: optional period end
        :return: float average km (0 if no missions)
        """
        self.ensure_one()
        Mission = self.env['fleet.mission']
        domain = self._get_driver_missions_domain(
            driver, date_from, date_to, exclude_zero_km=True
        )
        missions = Mission.search(domain)
        
        if not missions:
            return 0.0
        
        total_km = sum(missions.mapped('distance_km'))
        return total_km / len(missions)
    
    def _get_driver_missions_with_km_count(self, driver, date_from=None, date_to=None):
        """
        Count completed missions that have km data (distance_km > 0).
        
        :param driver: res.partner recordset
        :param date_from: optional period start
        :param date_to: optional period end
        :return: integer count
        """
        self.ensure_one()
        Mission = self.env['fleet.mission']
        domain = self._get_driver_missions_domain(
            driver, date_from, date_to, exclude_zero_km=True
        )
        return Mission.search_count(domain)
    
    # ==========================================================================
    # Action Methods (Smart Buttons)
    # ==========================================================================
    
    def action_view_registration_cases(self):
        """Open registration cases for this vehicle."""
        self.ensure_one()
        return {
            'name': _('Dossiers Immatriculation - %s', self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.registration.case',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
    
    def action_view_transfers(self):
        """Open transfers for this vehicle."""
        self.ensure_one()
        return {
            'name': _('Transferts - %s', self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.transfer',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
    
    def action_view_state_history(self):
        """Open state history (tracking values) for this vehicle."""
        self.ensure_one()
        history = self._get_state_history()
        return {
            'name': _('Historique États - %s', self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.tracking.value',
            'view_mode': 'list',
            'domain': [('id', 'in', history.ids)],
            'context': {'create': False, 'edit': False, 'delete': False},
        }
