# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.vehicle for SCORE compliance.

Adds helper fields/methods to check for expired critical documents (FR-007a).

Fields added:
- has_expired_critical_docs: Boolean indicating vehicle has expired critical docs
- has_expired_docs: Boolean indicating vehicle has any expired docs
- has_expiring_soon_docs: Boolean indicating docs expiring within alert period
- expired_critical_doc_ids: One2many to expired critical documents
- compliance_status: Selection showing overall compliance status
"""

from datetime import date, timedelta

from odoo import _, api, fields, models


class FleetVehicle(models.Model):
    """Extend vehicle with document compliance helper fields."""
    
    _inherit = 'fleet.vehicle'
    
    # =========================================================================
    # COMPLIANCE STATUS FIELDS
    # =========================================================================
    
    has_expired_critical_docs = fields.Boolean(
        string='Documents Critiques Expirés',
        compute='_compute_document_compliance_status',
        store=True,
        help="Indique si le véhicule a des documents critiques expirés "
             "(ex: Assurance, Visite Technique). Ces documents bloquent les missions."
    )
    
    has_expired_docs = fields.Boolean(
        string='Documents Expirés',
        compute='_compute_document_compliance_status',
        store=True,
        help="Indique si le véhicule a des documents expirés (critiques ou non)."
    )
    
    has_expiring_soon_docs = fields.Boolean(
        string='Documents Expirant Bientôt',
        compute='_compute_document_compliance_status',
        store=True,
        help="Indique si le véhicule a des documents arrivant à échéance "
             "dans le délai d'alerte configuré (J-30 par défaut)."
    )
    
    expired_critical_doc_count = fields.Integer(
        string='Nb Documents Critiques Expirés',
        compute='_compute_document_compliance_status',
        store=True,
        help="Nombre de documents critiques expirés."
    )
    
    expired_doc_count = fields.Integer(
        string='Nb Documents Expirés',
        compute='_compute_document_compliance_status',
        store=True,
        help="Nombre total de documents expirés."
    )
    
    expiring_soon_doc_count = fields.Integer(
        string='Nb Documents Expirant Bientôt',
        compute='_compute_document_compliance_status',
        store=True,
        help="Nombre de documents arrivant à échéance."
    )
    
    compliance_status = fields.Selection(
        [
            ('ok', 'Conforme'),
            ('warning', 'Attention'),
            ('blocked', 'Bloqué'),
        ],
        string='Statut Conformité',
        compute='_compute_document_compliance_status',
        store=True,
        help="Statut global de conformité documentaire:\n"
             "- Conforme: Tous les documents sont valides\n"
             "- Attention: Documents expirant bientôt ou non-critiques expirés\n"
             "- Bloqué: Documents critiques expirés (missions bloquées)"
    )
    
    compliance_message = fields.Char(
        string='Message Conformité',
        compute='_compute_document_compliance_status',
        help="Message décrivant l'état de conformité documentaire."
    )
    
    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('document_ids', 'document_ids.expiry_date', 'document_ids.state',
                 'document_ids.is_critical_document')
    def _compute_document_compliance_status(self):
        """Compute document compliance status for vehicles.
        
        Computes:
        - has_expired_critical_docs
        - has_expired_docs
        - has_expiring_soon_docs
        - expired_critical_doc_count
        - expired_doc_count
        - expiring_soon_doc_count
        - compliance_status
        - compliance_message
        """
        today = date.today()
        
        # Get alert days from config
        ConfigParam = self.env['ir.config_parameter'].sudo()
        alert_days = int(ConfigParam.get_param(
            'custom_score_compliance.alert_days_before_expiry', '30'
        ))
        alert_date = today + timedelta(days=alert_days)
        
        for vehicle in self:
            # Get active documents (not cancelled/draft)
            active_docs = vehicle.document_ids.filtered(
                lambda d: d.state not in ('cancelled', 'draft')
            )
            
            # Expired documents (any)
            expired_docs = active_docs.filtered(
                lambda d: d.expiry_date and d.expiry_date < today
            )
            
            # Expired critical documents
            expired_critical_docs = expired_docs.filtered('is_critical_document')
            
            # Expiring soon (within alert period, not yet expired)
            expiring_soon_docs = active_docs.filtered(
                lambda d: d.expiry_date and today <= d.expiry_date <= alert_date
            )
            
            # Set counts
            vehicle.expired_doc_count = len(expired_docs)
            vehicle.expired_critical_doc_count = len(expired_critical_docs)
            vehicle.expiring_soon_doc_count = len(expiring_soon_docs)
            
            # Set boolean flags
            vehicle.has_expired_docs = bool(expired_docs)
            vehicle.has_expired_critical_docs = bool(expired_critical_docs)
            vehicle.has_expiring_soon_docs = bool(expiring_soon_docs)
            
            # Determine compliance status
            if expired_critical_docs:
                vehicle.compliance_status = 'blocked'
                vehicle.compliance_message = _(
                    "%d document(s) critique(s) expiré(s) - Missions bloquées"
                ) % len(expired_critical_docs)
            elif expired_docs or expiring_soon_docs:
                vehicle.compliance_status = 'warning'
                parts = []
                if expired_docs:
                    parts.append(_("%d document(s) expiré(s)") % len(expired_docs))
                if expiring_soon_docs:
                    parts.append(_("%d document(s) expirant bientôt") % len(expiring_soon_docs))
                vehicle.compliance_message = ", ".join(parts)
            else:
                vehicle.compliance_status = 'ok'
                vehicle.compliance_message = _("Tous les documents sont à jour")
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def get_expired_critical_docs(self):
        """Get expired critical documents for this vehicle.
        
        Returns:
            fleet.vehicle.document recordset
        """
        self.ensure_one()
        today = date.today()
        return self.document_ids.filtered(
            lambda d: (
                d.state not in ('cancelled', 'draft') and
                d.is_critical_document and
                d.expiry_date and
                d.expiry_date < today
            )
        )
    
    def get_expired_docs(self):
        """Get all expired documents for this vehicle.
        
        Returns:
            fleet.vehicle.document recordset
        """
        self.ensure_one()
        today = date.today()
        return self.document_ids.filtered(
            lambda d: (
                d.state not in ('cancelled', 'draft') and
                d.expiry_date and
                d.expiry_date < today
            )
        )
    
    def get_expiring_soon_docs(self, days=None):
        """Get documents expiring soon for this vehicle.
        
        Args:
            days: Number of days to look ahead (default from config)
            
        Returns:
            fleet.vehicle.document recordset
        """
        self.ensure_one()
        today = date.today()
        
        if days is None:
            ConfigParam = self.env['ir.config_parameter'].sudo()
            days = int(ConfigParam.get_param(
                'custom_score_compliance.alert_days_before_expiry', '30'
            ))
        
        alert_date = today + timedelta(days=days)
        
        return self.document_ids.filtered(
            lambda d: (
                d.state not in ('cancelled', 'draft') and
                d.expiry_date and
                today <= d.expiry_date <= alert_date
            )
        )
    
    def get_compliance_blocking_reasons(self):
        """Get list of reasons blocking this vehicle from missions.
        
        Returns:
            list: List of blocking reason strings
        """
        self.ensure_one()
        reasons = []
        
        expired_critical = self.get_expired_critical_docs()
        for doc in expired_critical:
            type_label = doc.get_document_type_label()
            reasons.append(_(
                "%(type)s expiré(e) le %(date)s",
                type=type_label,
                date=doc.expiry_date.strftime('%d/%m/%Y')
            ))
        
        return reasons
    
    def check_mission_allowed(self, raise_error=False):
        """Check if this vehicle can be used for a mission.
        
        Args:
            raise_error: If True, raise UserError instead of returning False
            
        Returns:
            bool: True if missions are allowed, False otherwise
            
        Raises:
            UserError: If raise_error=True and missions are blocked
        """
        self.ensure_one()
        
        if not self.has_expired_critical_docs:
            return True
        
        if raise_error:
            reasons = self.get_compliance_blocking_reasons()
            from odoo.exceptions import UserError
            raise UserError(_(
                "Impossible d'utiliser ce véhicule pour une mission.\n\n"
                "Documents critiques expirés:\n%(reasons)s\n\n"
                "Veuillez renouveler ces documents avant de créer une mission.",
                reasons="\n".join(f"• {r}" for r in reasons)
            ))
        
        return False
    
    # =========================================================================
    # ACTIONS
    # =========================================================================
    
    def action_view_expired_docs(self):
        """Action to view expired documents for this vehicle."""
        self.ensure_one()
        expired_docs = self.get_expired_docs()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents Expirés - %s') % self.name,
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', expired_docs.ids)],
            'context': {'default_vehicle_id': self.id},
        }
    
    def action_view_expiring_soon_docs(self):
        """Action to view documents expiring soon for this vehicle."""
        self.ensure_one()
        expiring_docs = self.get_expiring_soon_docs()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents Expirant Bientôt - %s') % self.name,
            'res_model': 'fleet.vehicle.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', expiring_docs.ids)],
            'context': {'default_vehicle_id': self.id},
        }
    
    # =========================================================================
    # CRON METHODS
    # =========================================================================
    
    @api.model
    def _cron_recompute_compliance_status(self):
        """Cron: Recompute compliance status for all active vehicles.
        
        Called daily by scheduled action ir_cron_vehicle_compliance_recompute.
        Forces recomputation of stored computed fields for dashboard/reports.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # Get all active vehicles
        vehicles = self.search([('active', '=', True)])
        
        if not vehicles:
            _logger.info("SCORE Compliance: No active vehicles to recompute")
            return
        
        _logger.info("SCORE Compliance: Recomputing compliance for %d vehicles", len(vehicles))
        
        # Invalidate cache and recompute
        vehicles.invalidate_recordset(['has_expired_critical_docs', 'has_expired_docs',
                                       'has_expiring_soon_docs', 'compliance_status'])
        
        # Trigger recomputation by reading the fields
        for vehicle in vehicles:
            # Force recompute
            _ = vehicle.compliance_status
        
        _logger.info("SCORE Compliance: Compliance recomputation complete")
