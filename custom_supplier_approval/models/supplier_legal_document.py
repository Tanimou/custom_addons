# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SupplierLegalDocument(models.Model):
    """Legal documents for suppliers (RCCM, NCC, CNPS, etc.)"""
    _name = 'supplier.legal.document'
    _description = 'Supplier Legal Document'
    _order = 'issue_date desc, id desc'

    name = fields.Char(
        string='Document Name',
        compute='_compute_name',
        store=True,
        help="Automatically generated document name"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        ondelete='cascade',
        index=True,
        help="Supplier to whom this document belongs"
    )
    document_type = fields.Selection(
        selection=[
            ('rccm', 'RCCM (Trade Register)'),
            ('ncc', 'NCC (Tax ID)'),
            ('cnps', 'CNPS (Social Security)'),
            ('patent', 'Patent/Business License'),
            ('insurance', 'Insurance Certificate'),
            ('attestation', 'Tax Clearance Certificate'),
            ('other', 'Other Document'),
        ],
        string='Document Type',
        required=True,
        help="Type of legal document"
    )
    document_number = fields.Char(
        string='Document Number',
        help="Official document reference number"
    )
    issue_date = fields.Date(
        string='Issue Date',
        help="Date when the document was issued"
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        help="Date when the document expires (if applicable)"
    )
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Attachment',
        help="Scanned copy or PDF of the document",
        ondelete='restrict'
    )
    state = fields.Selection(
        selection=[
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('pending', 'Pending Verification'),
        ],
        string='Status',
        compute='_compute_state',
        store=True,
        default='pending',
        help="Document validity status"
    )
    notes = fields.Text(
        string='Notes',
        help="Additional notes about this document"
    )

    _sql_constraints = [
        ('check_dates', 'CHECK(expiry_date IS NULL OR expiry_date >= issue_date)',
         'Expiry date must be after issue date!'),
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
                doc.name = _('New Document')

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
                raise ValidationError(_('Issue date cannot be in the future!'))

    def action_view_attachment(self):
        """Action to view/download the document attachment"""
        self.ensure_one()
        if not self.attachment_id:
            raise ValidationError(_('No attachment found for this document.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'new',
        }
