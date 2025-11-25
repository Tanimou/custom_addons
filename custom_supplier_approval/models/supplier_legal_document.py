# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SupplierLegalDocument(models.Model):
    """Legal documents for suppliers (RCCM, NCC, CNPS, etc.)"""
    _name = 'supplier.legal.document'
    _description = 'Supplier Legal Document'
    _inherit = ['mail.thread']
    _order = 'issue_date desc, id desc'

    name = fields.Char(
        string='Nom du document',
        compute='_compute_name',
        store=True,
        help="Nom du document généré automatiquement"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        required=True,
        ondelete='cascade',
        index=True,
        help="Fournisseur auquel ce document appartient"
    )
    document_type = fields.Selection(
        selection=[
            ('rccm', 'RCCM (Registre de commerce)'),
            ('ncc', 'NCC (Identifiant fiscal)'),
            ('cnps', 'CNPS (Sécurité sociale)'),
            ('patent', 'Brevet/Licence commerciale'),
            ('insurance', 'Certificat d\'assurance'),
            ('attestation', 'Attestation de régularité fiscale'),
            ('other', 'Autre document'),
        ],
        string='Type de document',
        required=True,
        help="Type de document légal"
    )
    document_number = fields.Char(
        string='Numéro du document',
        help="Numéro de référence officiel du document"
    )
    issue_date = fields.Date(
        string='Date de délivrance',
        help="Date à laquelle le document a été délivré"
    )
    expiry_date = fields.Date(
        string='Date d\'expiration',
        help="Date à laquelle le document expire (le cas échéant)"
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Pièce jointe',
        help="Copie scannée ou PDF du document",
        ondelete='restrict'
    )
    attachment_name = fields.Char(
        related='attachment_id.name',
        string='Nom du fichier',
        readonly=False
    )
    state = fields.Selection(
        selection=[
            ('valid', 'Valide'),
            ('expired', 'Expiré'),
            ('pending', 'En attente de vérification'),
        ],
        string='Statut',
        compute='_compute_state',
        store=True,
        default='pending',
        help="Statut de validité du document"
    )
    notes = fields.Text(
        string='Notes',
        help="Notes supplémentaires sur ce document"
    )

    _sql_constraints = [
        ('check_dates', 'CHECK(expiry_date IS NULL OR expiry_date >= issue_date)',
         'La date d\'expiration doit être postérieure à la date de délivrance !'),
    ]

    @api.depends('partner_id', 'document_type', 'document_number')
    def _compute_name(self):
        """Generate automatic document name"""
        for doc in self:
            if doc.partner_id and doc.document_type:
                doc_type_label = dict(self._fields['document_type'].selection).get(doc.document_type, '')
                doc.name = f"{doc.partner_id.name} - {doc_type_label}"
                if doc.document_number:
                    doc.name += f" ({doc.document_number})"
            else:
                doc.name = _('Nouveau Document')

    @api.depends('expiry_date', 'issue_date')
    def _compute_state(self):
        """Compute document state based on expiry date"""
        today = date.today()
        for doc in self:
            if not doc.expiry_date:
                # No expiry date means document doesn't expire
                doc.state = 'valid' if doc.issue_date else 'pending'
            elif doc.expiry_date < today:
                doc.state = 'expired'
            else:
                doc.state = 'valid'

    @api.constrains('issue_date')
    def _check_issue_date(self):
        """Ensure issue date is not in the future"""
        today = date.today()
        for doc in self:
            if doc.issue_date and doc.issue_date > today:
                raise ValidationError(_('La date de délivrance ne peut pas être dans le futur !'))

    def action_view_attachment(self):
        """Action to view/download the document attachment"""
        self.ensure_one()
        if not self.attachment_id:
            raise ValidationError(_('Aucune pièce jointe trouvée pour ce document.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'new',
        }
