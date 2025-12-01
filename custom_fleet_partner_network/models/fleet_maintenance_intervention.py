# -*- coding: utf-8 -*-
"""Extension of fleet.maintenance.intervention for incident ticket synchronization.

This module adds the incident_ticket_id field and bidirectional state synchronization
between fleet.incident.ticket and fleet.maintenance.intervention.
"""

from odoo import _, api, fields, models


class FleetMaintenanceInterventionExtension(models.Model):
    """Extend fleet.maintenance.intervention with incident ticket linking."""
    
    _inherit = "fleet.maintenance.intervention"

    # Link to incident ticket (set when ticket creates or links an intervention)
    incident_ticket_id = fields.Many2one(
        "fleet.incident.ticket",
        string="Ticket d'incident lié",
        tracking=True,
        help="Ticket d'incident lié à cette intervention",
    )

    def write(self, vals):
        """Override write to sync state to linked incident ticket."""
        res = super().write(vals)
        # Synchronize state to linked incident ticket (avoid infinite loop)
        if "state" in vals and not self.env.context.get("_sync_from_ticket"):
            self._sync_state_to_ticket(vals["state"])
        return res

    def _sync_state_to_ticket(self, intervention_state):
        """Synchronize intervention state to linked incident ticket.
        
        State mapping:
        - in_progress → repair
        - done → closed
        - cancelled → cancelled
        """
        state_mapping = {
            "in_progress": "repair",
            "done": "closed",
            "cancelled": "cancelled",
        }
        ticket_state = state_mapping.get(intervention_state)
        if not ticket_state:
            return
        
        for record in self:
            if record.incident_ticket_id:
                # Check if ticket state needs to be updated
                current_ticket_state = record.incident_ticket_id.state
                if current_ticket_state != ticket_state:
                    # Use context flag to prevent infinite loop
                    record.incident_ticket_id.with_context(
                        _sync_from_intervention=True
                    ).write({"state": ticket_state})
