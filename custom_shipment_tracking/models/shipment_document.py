# -*- coding: utf-8 -*-
"""Shipment Document model for tracking required documents per shipment."""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShipmentDocument(models.Model):
    """Track documents required for shipment (FDI, DCVI, Déclaration, LTA)."""

    _name = 'shipment.document'
    _description = 'Document d\'expédition'
    _order = 'sequence, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # region Fields
    shipment_request_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande d\'expédition',
        required=True,
        ondelete='cascade',
        index=True,
    )
    document_type = fields.Selection(
        selection=[
            ('fdi', 'FDI - Facture Détaillée d\'Importation'),
            ('dcvi', 'DCVI - Déclaration en Douane Côte d\'Ivoire'),
            ('declaration', 'Déclaration de contenu'),
            ('lta', 'N° LTA - Lettre de Transport Aérien'),
        ],
        string='Type de document',
        required=True,
        tracking=True,
    )
    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )
    state = fields.Selection(
        selection=[
            ('to_prepare', 'À préparer'),
            ('in_progress', 'En cours'),
            ('ready', 'Prêt'),
            ('validated', 'Validé'),
        ],
        string='État',
        default='to_prepare',
        required=True,
        tracking=True,
        group_expand='_expand_states',
    )
    responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsable',
        tracking=True,
        default=lambda self: self.env.user,
    )
    deadline = fields.Date(
        string='Date limite',
        tracking=True,
    )
    reference = fields.Char(
        string='Référence / Numéro',
        help='Numéro du document (ex: N° LTA, N° FDI)',
        tracking=True,
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='shipment_document_attachment_rel',
        column1='document_id',
        column2='attachment_id',
        string='Pièces jointes',
    )
    attachment_count = fields.Integer(
        string='Nombre de pièces jointes',
        compute='_compute_attachment_count',
    )
    notes = fields.Text(
        string='Notes',
    )
    validation_date = fields.Datetime(
        string='Date de validation',
        readonly=True,
    )
    validated_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Validé par',
        readonly=True,
    )
    color = fields.Integer(
        string='Couleur',
        compute='_compute_color',
    )
    sequence = fields.Integer(
        string='Séquence',
        default=10,
    )
    # Related fields for display
    partner_id = fields.Many2one(
        related='shipment_request_id.partner_id',
        string='Client',
        store=True,
    )
    shipment_state = fields.Selection(
        related='shipment_request_id.state',
        string='État expédition',
    )
    company_id = fields.Many2one(
        related='shipment_request_id.company_id',
        string='Société',
        store=True,
    )
    # endregion

    # region Computes
    @api.depends('document_type', 'shipment_request_id.name')
    def _compute_name(self):
        """Compute document name from type and shipment."""
        type_labels = dict(self._fields['document_type'].selection)
        for record in self:
            type_label = type_labels.get(record.document_type, '')
            shipment_name = record.shipment_request_id.name or ''
            record.name = f"{type_label} - {shipment_name}"

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments."""
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends('state')
    def _compute_color(self):
        """Compute color based on state for Kanban view.
        
        Colors: 1=red, 2=orange, 3=yellow, 4=light blue, 10=green
        """
        color_map = {
            'to_prepare': 1,    # Red
            'in_progress': 2,   # Orange
            'ready': 3,         # Yellow
            'validated': 10,    # Green
        }
        for record in self:
            record.color = color_map.get(record.state, 0)

    @api.model
    def _expand_states(self, states, domain):
        """Expand all states in Kanban view even if empty."""
        return [key for key, _ in self._fields['state'].selection]
    # endregion

    # region Actions
    def action_set_in_progress(self):
        """Move document to 'En cours' state."""
        self.write({'state': 'in_progress'})

    def action_set_ready(self):
        """Move document to 'Prêt' state."""
        self.write({'state': 'ready'})

    def action_validate(self):
        """Validate the document."""
        for record in self:
            if not record.reference and record.document_type == 'lta':
                raise UserError("Veuillez saisir le numéro LTA avant de valider.")
            if not record.attachment_ids:
                raise UserError("Veuillez joindre au moins un fichier avant de valider.")
        
        self.write({
            'state': 'validated',
            'validation_date': fields.Datetime.now(),
            'validated_by_id': self.env.user.id,
        })
        
        # Check if all documents are validated for each shipment
        for record in self:
            record.shipment_request_id._check_document_validation_complete()

    def action_reset_to_prepare(self):
        """Reset document to 'À préparer' state."""
        self.write({
            'state': 'to_prepare',
            'validation_date': False,
            'validated_by_id': False,
        })

    def action_view_attachments(self):
        """Open attachments view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pièces jointes',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }
    # endregion

    # region Constraints
    _sql_constraints = [
        (
            'unique_document_per_shipment',
            'UNIQUE(shipment_request_id, document_type)',
            'Un seul document de chaque type par expédition!'
        ),
    ]
    # endregion
