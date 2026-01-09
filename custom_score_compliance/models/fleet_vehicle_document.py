# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.vehicle.document for SCORE compliance.

Adds document_type_id Many2one field for dynamic document types,
while maintaining backward compatibility with legacy Selection field.

Migration approach:
- Add document_type_id (Many2one to fleet.vehicle.document.type)
- Keep document_type Selection for backward compatibility
- Compute is_critical_document from document_type_id.is_critical
- Business logic prioritizes document_type_id when set
"""

from odoo import _, api, fields, models


class FleetVehicleDocument(models.Model):
    """Extend vehicle document with Many2one document type and criticality."""
    
    _inherit = 'fleet.vehicle.document'
    
    # =========================================================================
    # NEW FIELDS (Selection → Many2one migration)
    # =========================================================================
    
    document_type_id = fields.Many2one(
        'fleet.vehicle.document.type',
        string='Type de Document (Nouveau)',
        index=True,
        ondelete='restrict',
        help="Type de document (remplace le champ Selection). "
             "Permet de gérer dynamiquement les types et leur criticité."
    )
    
    is_critical_document = fields.Boolean(
        string='Document Critique',
        compute='_compute_is_critical_document',
        store=True,
        help="Calculé automatiquement selon le type de document. "
             "Les documents critiques expirés bloquent les missions."
    )
    
    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('document_type_id', 'document_type_id.is_critical', 'document_type')
    def _compute_is_critical_document(self):
        """Compute if document is critical based on document type.
        
        Priority:
        1. document_type_id.is_critical (if Many2one is set)
        2. Fallback to legacy Selection mapping for known critical types
        """
        # Legacy critical types (before Many2one migration)
        LEGACY_CRITICAL_TYPES = {'assurance', 'visite_technique'}
        
        for doc in self:
            if doc.document_type_id:
                # Use Many2one criticality flag
                doc.is_critical_document = doc.document_type_id.is_critical
            elif doc.document_type:
                # Fallback to legacy Selection mapping
                doc.is_critical_document = doc.document_type in LEGACY_CRITICAL_TYPES
            else:
                doc.is_critical_document = False
    
    # =========================================================================
    # OVERRIDE METHODS
    # =========================================================================
    
    @api.depends('vehicle_id', 'document_type', 'document_type_id', 'document_number')
    def _compute_name(self):
        """Override name computation to use document_type_id when available."""
        for doc in self:
            # Determine type label
            if doc.document_type_id:
                type_label = doc.document_type_id.name
            elif doc.document_type:
                type_label = dict(doc._fields['document_type'].selection).get(
                    doc.document_type, 'Document'
                )
            else:
                type_label = 'Document'
            
            vehicle_name = doc.vehicle_id.name if doc.vehicle_id else 'N/A'
            
            if doc.document_number:
                doc.name = f"{type_label} - {vehicle_name} - N°{doc.document_number}"
            else:
                doc.name = f"{type_label} - {vehicle_name}"
    
    @api.onchange('document_type_id')
    def _onchange_document_type_id(self):
        """Sync legacy Selection field when Many2one is changed."""
        if self.document_type_id and self.document_type_id.code:
            # Try to set legacy field if code matches Selection value
            legacy_selection_keys = dict(self._fields['document_type'].selection).keys()
            if self.document_type_id.code in legacy_selection_keys:
                self.document_type = self.document_type_id.code
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def get_document_type_label(self):
        """Get human-readable document type label.
        
        Returns:
            str: Document type name from Many2one or Selection
        """
        self.ensure_one()
        if self.document_type_id:
            return self.document_type_id.name
        elif self.document_type:
            return dict(self._fields['document_type'].selection).get(
                self.document_type, 'Autre'
            )
        return 'Non défini'
    
    @api.model
    def search_expired_critical(self, vehicle_ids=None, limit=None):
        """Search for expired critical documents.
        
        Args:
            vehicle_ids: Optional list of vehicle IDs to filter
            limit: Optional limit on results
            
        Returns:
            fleet.vehicle.document recordset
        """
        from datetime import date
        
        domain = [
            ('is_critical_document', '=', True),
            ('expiry_date', '<', date.today()),
            ('state', 'not in', ['cancelled', 'draft']),
        ]
        
        if vehicle_ids:
            domain.append(('vehicle_id', 'in', vehicle_ids))
        
        return self.search(domain, limit=limit)
    
    @api.model
    def search_expiring_soon(self, days=30, vehicle_ids=None, critical_only=False):
        """Search for documents expiring soon (within days).
        
        Args:
            days: Number of days to consider "expiring soon"
            vehicle_ids: Optional list of vehicle IDs to filter
            critical_only: If True, only return critical documents
            
        Returns:
            fleet.vehicle.document recordset
        """
        from datetime import date, timedelta
        
        domain = [
            ('expiry_date', '>=', date.today()),
            ('expiry_date', '<=', date.today() + timedelta(days=days)),
            ('state', 'not in', ['cancelled', 'draft']),
        ]
        
        if vehicle_ids:
            domain.append(('vehicle_id', 'in', vehicle_ids))
        
        if critical_only:
            domain.append(('is_critical_document', '=', True))
        
        return self.search(domain)
    
    # =========================================================================
    # CRON METHODS (FR-007: J-30 alerts and weekly reminders)
    # =========================================================================
    
    @api.model
    def _cron_send_expiry_alerts(self, days_before=30):
        """Cron: Send alerts for documents expiring soon (J-30 by default).
        
        Called daily by scheduled action ir_cron_document_expiry_j30_alert.
        Sends activity notifications to fleet managers.
        
        Args:
            days_before: Number of days before expiry to send alert
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        expiring_docs = self.search_expiring_soon(days=days_before, critical_only=True)
        
        if not expiring_docs:
            _logger.info("SCORE Compliance: No critical documents expiring in %d days", days_before)
            return
        
        _logger.info(
            "SCORE Compliance: Found %d critical documents expiring in %d days",
            len(expiring_docs), days_before
        )
        
        # Group by vehicle for consolidated notifications
        by_vehicle = {}
        for doc in expiring_docs:
            if doc.vehicle_id not in by_vehicle:
                by_vehicle[doc.vehicle_id] = self.env['fleet.vehicle.document']
            by_vehicle[doc.vehicle_id] |= doc
        
        # Get fleet managers to notify
        fleet_manager_group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
        if not fleet_manager_group:
            _logger.warning("SCORE Compliance: Fleet manager group not found, skipping notifications")
            return
        
        managers = self.env['res.users'].search([
            ('groups_id', 'in', fleet_manager_group.id),
            ('active', '=', True),
        ])
        
        if not managers:
            _logger.warning("SCORE Compliance: No fleet managers found, skipping notifications")
            return
        
        # Create activities for each vehicle's expiring documents
        activity_type = self.env.ref('mail.mail_activity_data_warning', raise_if_not_found=False)
        if not activity_type:
            _logger.warning("SCORE Compliance: Warning activity type not found")
            return
        
        for vehicle, docs in by_vehicle.items():
            doc_names = ', '.join(docs.mapped('name'))
            summary = _("Documents critiques expirant bientôt: %s") % doc_names
            
            # Create activity on vehicle for first manager
            try:
                vehicle.activity_schedule(
                    'mail.mail_activity_data_warning',
                    note=_("Les documents suivants expirent dans les %d prochains jours:\n%s") % (
                        days_before,
                        '\n'.join(['- ' + d.name + ' (expire le ' + str(d.expiry_date) + ')' for d in docs])
                    ),
                    summary=summary[:100],  # Truncate to fit
                    user_id=managers[0].id,
                )
            except Exception as e:
                _logger.error("SCORE Compliance: Failed to create activity for vehicle %s: %s", vehicle.name, e)
        
        _logger.info("SCORE Compliance: J-%d alerts sent for %d vehicles", days_before, len(by_vehicle))
    
    @api.model
    def _cron_send_expired_reminders(self):
        """Cron: Send weekly reminders for already expired documents.
        
        Called weekly by scheduled action ir_cron_document_expired_weekly_reminder.
        Sends consolidated reminder to fleet managers.
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        expired_docs = self.search_expired_critical()
        
        if not expired_docs:
            _logger.info("SCORE Compliance: No expired critical documents found")
            return
        
        _logger.info("SCORE Compliance: Found %d expired critical documents", len(expired_docs))
        
        # Group by vehicle
        by_vehicle = {}
        for doc in expired_docs:
            if doc.vehicle_id not in by_vehicle:
                by_vehicle[doc.vehicle_id] = self.env['fleet.vehicle.document']
            by_vehicle[doc.vehicle_id] |= doc
        
        # Get fleet managers
        fleet_manager_group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
        if not fleet_manager_group:
            return
        
        managers = self.env['res.users'].search([
            ('groups_id', 'in', fleet_manager_group.id),
            ('active', '=', True),
        ])
        
        if not managers:
            return
        
        # Send one consolidated message to first manager
        body_lines = [_("<h3>Rappel: Documents Critiques Expirés</h3>")]
        body_lines.append(_("<p>Les véhicules suivants ont des documents critiques expirés "
                           "et ne peuvent pas être utilisés pour des missions:</p>"))
        body_lines.append("<ul>")
        
        for vehicle, docs in by_vehicle.items():
            body_lines.append("<li><b>%s</b>:<ul>" % vehicle.name)
            for doc in docs:
                body_lines.append("<li>%s (expiré le %s)</li>" % (doc.name, doc.expiry_date))
            body_lines.append("</ul></li>")
        
        body_lines.append("</ul>")
        
        # Post message to first manager
        try:
            managers[0].partner_id.message_post(
                body=''.join(body_lines),
                subject=_("SCORE: Rappel hebdomadaire - %d documents expirés") % len(expired_docs),
                message_type='notification',
            )
            _logger.info("SCORE Compliance: Weekly reminder sent for %d expired documents", len(expired_docs))
        except Exception as e:
            _logger.error("SCORE Compliance: Failed to send weekly reminder: %s", e)
