# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.mission for SCORE compliance.

Implements mission blocking when vehicle has expired critical documents (FR-007a).

Blocking behavior (configurable via settings):
- Block on submit: True by default
- Block on start: True by default
- Block on create: False by default (drafts allowed with warning)
- Warn on vehicle change: True by default

Non-critical expired docs trigger warnings but do not block.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FleetMission(models.Model):
    """Extend mission with document compliance blocking."""
    
    _inherit = 'fleet.mission'
    
    # =========================================================================
    # COMPLIANCE FIELDS
    # =========================================================================
    
    compliance_status = fields.Selection(
        related='vehicle_id.compliance_status',
        string='Statut Conformité Véhicule',
        store=True,
        help="Statut de conformité documentaire du véhicule assigné."
    )
    
    compliance_blocking_reason = fields.Text(
        string='Raison de Blocage',
        compute='_compute_compliance_blocking_reason',
        help="Détail des documents critiques expirés bloquant la mission."
    )
    
    has_compliance_warning = fields.Boolean(
        string='Avertissement Conformité',
        compute='_compute_compliance_blocking_reason',
        help="Indique si le véhicule a des documents expirés ou expirant bientôt."
    )
    
    compliance_warning_message = fields.Text(
        string='Message Avertissement',
        compute='_compute_compliance_blocking_reason',
        help="Détail des avertissements de conformité (non bloquants)."
    )
    
    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    @api.depends('vehicle_id', 'vehicle_id.has_expired_critical_docs',
                 'vehicle_id.has_expired_docs', 'vehicle_id.has_expiring_soon_docs')
    def _compute_compliance_blocking_reason(self):
        """Compute compliance blocking reason and warnings."""
        for mission in self:
            blocking_reasons = []
            warning_messages = []
            
            if mission.vehicle_id:
                # Get blocking reasons (critical expired)
                if mission.vehicle_id.has_expired_critical_docs:
                    blocking_reasons = mission.vehicle_id.get_compliance_blocking_reasons()
                
                # Get warnings (non-critical expired or expiring soon)
                expired_non_critical = mission.vehicle_id.get_expired_docs().filtered(
                    lambda d: not d.is_critical_document
                )
                for doc in expired_non_critical:
                    warning_messages.append(_(
                        "%(type)s expiré(e) le %(date)s (non bloquant)",
                        type=doc.get_document_type_label(),
                        date=doc.expiry_date.strftime('%d/%m/%Y')
                    ))
                
                expiring_soon = mission.vehicle_id.get_expiring_soon_docs()
                for doc in expiring_soon:
                    warning_messages.append(_(
                        "%(type)s expire le %(date)s",
                        type=doc.get_document_type_label(),
                        date=doc.expiry_date.strftime('%d/%m/%Y')
                    ))
            
            # Set fields
            mission.compliance_blocking_reason = "\n".join(blocking_reasons) if blocking_reasons else False
            mission.has_compliance_warning = bool(warning_messages) or bool(blocking_reasons)
            mission.compliance_warning_message = "\n".join(warning_messages) if warning_messages else False
    
    # =========================================================================
    # CONFIGURATION HELPERS
    # =========================================================================
    
    def _get_compliance_config(self):
        """Get compliance configuration settings.
        
        Returns:
            dict: Configuration values for blocking behavior
        """
        ConfigParam = self.env['ir.config_parameter'].sudo()
        
        return {
            'block_on_submit': ConfigParam.get_param(
                'custom_score_compliance.block_mission_on_submit', 'True'
            ) == 'True',
            'block_on_start': ConfigParam.get_param(
                'custom_score_compliance.block_mission_on_start', 'True'
            ) == 'True',
            'block_on_create': ConfigParam.get_param(
                'custom_score_compliance.block_mission_on_create', 'False'
            ) == 'True',
            'warn_on_vehicle_change': ConfigParam.get_param(
                'custom_score_compliance.warn_on_vehicle_change', 'True'
            ) == 'True',
        }
    
    def _check_compliance_blocking(self, action='submit'):
        """Check if mission is blocked due to compliance issues.
        
        Args:
            action: The action being performed ('create', 'submit', 'start')
            
        Raises:
            UserError: If mission is blocked due to expired critical documents
        """
        self.ensure_one()
        config = self._get_compliance_config()
        
        # Determine if this action should be blocked
        should_block = False
        if action == 'create' and config['block_on_create']:
            should_block = True
        elif action == 'submit' and config['block_on_submit']:
            should_block = True
        elif action == 'start' and config['block_on_start']:
            should_block = True
        
        if not should_block:
            return
        
        # Check vehicle compliance
        if self.vehicle_id and self.vehicle_id.has_expired_critical_docs:
            reasons = self.vehicle_id.get_compliance_blocking_reasons()
            
            action_labels = {
                'create': _("créer"),
                'submit': _("soumettre"),
                'start': _("démarrer"),
            }
            
            raise UserError(_(
                "Impossible de %(action)s cette mission.\n\n"
                "Le véhicule %(vehicle)s a des documents critiques expirés:\n"
                "%(reasons)s\n\n"
                "Veuillez renouveler ces documents avant de continuer.",
                action=action_labels.get(action, action),
                vehicle=self.vehicle_id.name,
                reasons="\n".join(f"• {r}" for r in reasons)
            ))
    
    # =========================================================================
    # ONCHANGE METHODS
    # =========================================================================
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id_compliance_warning(self):
        """Show warning when selecting a vehicle with compliance issues."""
        if not self.vehicle_id:
            return
        
        config = self._get_compliance_config()
        if not config['warn_on_vehicle_change']:
            return
        
        warnings = []
        
        # Critical expired docs (blocking)
        if self.vehicle_id.has_expired_critical_docs:
            reasons = self.vehicle_id.get_compliance_blocking_reasons()
            warnings.append(_(
                "⚠️ ATTENTION: Ce véhicule a des documents critiques expirés:\n%s\n\n"
                "Les missions avec ce véhicule seront bloquées.",
                "\n".join(f"• {r}" for r in reasons)
            ))
        
        # Non-critical expired docs (warning only)
        expired_non_critical = self.vehicle_id.get_expired_docs().filtered(
            lambda d: not d.is_critical_document
        )
        if expired_non_critical:
            doc_list = [
                f"• {d.get_document_type_label()} (expiré le {d.expiry_date.strftime('%d/%m/%Y')})"
                for d in expired_non_critical
            ]
            warnings.append(_(
                "Ce véhicule a des documents expirés (non bloquants):\n%s",
                "\n".join(doc_list)
            ))
        
        # Expiring soon docs
        expiring_soon = self.vehicle_id.get_expiring_soon_docs()
        if expiring_soon:
            doc_list = [
                f"• {d.get_document_type_label()} (expire le {d.expiry_date.strftime('%d/%m/%Y')})"
                for d in expiring_soon
            ]
            warnings.append(_(
                "Ce véhicule a des documents expirant bientôt:\n%s",
                "\n".join(doc_list)
            ))
        
        if warnings:
            return {
                'warning': {
                    'title': _('Conformité Documentaire'),
                    'message': "\n\n".join(warnings),
                    'type': 'notification' if not self.vehicle_id.has_expired_critical_docs else 'warning',
                }
            }
    
    # =========================================================================
    # OVERRIDE WORKFLOW METHODS
    # =========================================================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to check compliance blocking if configured."""
        missions = super().create(vals_list)
        
        # Check compliance blocking on create (if enabled)
        config = self._get_compliance_config()
        if config['block_on_create']:
            for mission in missions:
                mission._check_compliance_blocking('create')
        
        return missions
    
    def action_submit(self):
        """Override submit action to check compliance blocking."""
        for mission in self:
            mission._check_compliance_blocking('submit')
        
        return super().action_submit()
    
    def action_start(self):
        """Override start action to check compliance blocking."""
        for mission in self:
            mission._check_compliance_blocking('start')
        
        return super().action_start()
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def get_compliance_summary(self):
        """Get compliance summary for this mission.
        
        Returns:
            dict: Summary with status, blocking reasons, and warnings
        """
        self.ensure_one()
        
        return {
            'status': self.compliance_status,
            'is_blocked': bool(self.compliance_blocking_reason),
            'blocking_reasons': self.compliance_blocking_reason.split('\n') if self.compliance_blocking_reason else [],
            'has_warning': self.has_compliance_warning,
            'warnings': self.compliance_warning_message.split('\n') if self.compliance_warning_message else [],
        }
