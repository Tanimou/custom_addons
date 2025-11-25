# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MissionCancellationWizard(models.TransientModel):
    """Wizard to cancel a fleet mission with reason"""
    _name = 'fleet.mission.cancellation.wizard'
    _description = 'Mission Cancellation Wizard'

    mission_id = fields.Many2one(
        'fleet.mission',
        string='Mission',
        required=True,
        readonly=True
    )
    mission_name = fields.Char(
        related='mission_id.name',
        string='Référence Mission',
        readonly=True
    )
    vehicle_name = fields.Char(
        related='mission_id.vehicle_id.name',
        string='Véhicule',
        readonly=True
    )
    cancellation_reason = fields.Text(
        string='Motif d\'annulation',
        required=True,
        help="Veuillez indiquer la raison de l'annulation de cette mission"
    )

    def action_confirm_cancellation(self):
        """Confirm the cancellation with the provided reason"""
        self.ensure_one()
        if not self.cancellation_reason:
            raise UserError(_('Veuillez fournir un motif d\'annulation!'))
        
        # Write the cancellation reason and cancel the mission
        old_state = self.mission_id.state
        self.mission_id.write({
            'state': 'cancelled',
            'cancellation_reason': self.cancellation_reason,
        })
        
        # Delete calendar event if exists
        if self.mission_id.calendar_event_id:
            self.mission_id.calendar_event_id.unlink()
        
        # Post message in chatter
        state_labels = dict(self.mission_id._fields['state'].selection)
        self.mission_id.message_post(
            body=_("Mission annulée (état précédent: %s). Motif: %s") % (
                state_labels.get(old_state, old_state),
                self.cancellation_reason
            ),
            subject=_("Annulation")
        )
        
        return {'type': 'ir.actions.act_window_close'}
