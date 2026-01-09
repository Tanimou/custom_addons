# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Document type model for vehicle documents (FR-007).

This model replaces the Selection field approach for document types,
allowing dynamic management of document types with criticality flags.

Migration strategy:
- Add document_type_id Many2one field
- Keep legacy document_type Selection for compatibility
- Backfill existing documents on install via post_init_hook
- Business logic uses document_type_id when set, falls back to mapped Selection
"""

from odoo import _, api, fields, models


class FleetVehicleDocumentType(models.Model):
    """Master data for vehicle document types with criticality flag."""
    
    _name = 'fleet.vehicle.document.type'
    _description = 'Type de Document Véhicule'
    _order = 'sequence, name'
    _rec_name = 'name'

    # =========================================================================
    # FIELDS
    # =========================================================================
    
    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
        help="Nom du type de document (ex: Assurance, Visite Technique)"
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help="Code technique unique (ex: assurance, visite_technique). "
             "Utilisé pour la migration depuis l'ancien champ Selection."
    )
    
    is_critical = fields.Boolean(
        string='Document Critique',
        default=False,
        help="Si coché, l'expiration de ce document bloquera les missions. "
             "Exemples: Assurance, Visite Technique."
    )
    
    description = fields.Text(
        string='Description',
        translate=True,
        help="Description détaillée du type de document et de son utilisation."
    )
    
    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help="Ordre d'affichage dans les listes."
    )
    
    active = fields.Boolean(
        string='Actif',
        default=True,
        help="Décocher pour archiver ce type de document."
    )
    
    # =========================================================================
    # Related Fields for Statistics
    # =========================================================================
    
    document_count = fields.Integer(
        string='Nombre de Documents',
        compute='_compute_document_count',
        help="Nombre de documents utilisant ce type."
    )
    
    # =========================================================================
    # SQL CONSTRAINTS
    # =========================================================================
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 
         "Le code du type de document doit être unique!"),
        ('name_unique', 'UNIQUE(name)', 
         "Le nom du type de document doit être unique!"),
    ]
    
    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================
    
    def _compute_document_count(self):
        """Compute number of documents using this type."""
        Document = self.env['fleet.vehicle.document']
        for doc_type in self:
            doc_type.document_count = Document.search_count([
                ('document_type_id', '=', doc_type.id)
            ])
    
    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================
    
    @api.model
    def get_critical_types(self):
        """Return all critical document types."""
        return self.search([('is_critical', '=', True)])
    
    @api.model
    def get_type_by_code(self, code):
        """Get document type by its code (for migration/mapping).
        
        Args:
            code: Technical code (e.g., 'assurance', 'visite_technique')
            
        Returns:
            fleet.vehicle.document.type record or empty recordset
        """
        return self.search([('code', '=', code)], limit=1)
    
    @api.model
    def get_legacy_mapping(self):
        """Return mapping from legacy Selection values to document type codes.
        
        This mapping is used during migration from Selection to Many2one.
        The legacy Selection values are from fleet.vehicle.document.document_type.
        """
        return {
            'carte_grise': 'carte_grise',
            'assurance': 'assurance',
            'visite_technique': 'visite_technique',
            'vignette': 'vignette',
            'permis': 'permis',
            'controle_pollution': 'controle_pollution',
            'pv': 'pv',
            'maintenance': 'maintenance',
            'other': 'other',
        }


def _post_init_hook_backfill_document_types(env):
    """Post-init hook to backfill document_type_id from legacy Selection.
    
    Called after module installation to migrate existing documents
    from the Selection field to the Many2one field.
    
    This hook is registered in __manifest__.py:
        'post_init_hook': '_post_init_hook_backfill_document_types',
    """
    import logging
    _logger = logging.getLogger(__name__)
    
    Document = env['fleet.vehicle.document']
    DocType = env['fleet.vehicle.document.type']
    
    # Get mapping from legacy values to codes
    mapping = DocType.get_legacy_mapping()
    
    # Find documents with legacy Selection but no Many2one
    docs_to_migrate = Document.search([
        ('document_type_id', '=', False),
        ('document_type', '!=', False),
    ])
    
    if not docs_to_migrate:
        _logger.info("No documents to migrate from Selection to Many2one")
        return
    
    _logger.info("Migrating %d documents from Selection to Many2one", len(docs_to_migrate))
    
    migrated = 0
    errors = 0
    
    for doc in docs_to_migrate:
        legacy_value = doc.document_type
        
        if not legacy_value:
            continue
        
        # Get the code from mapping (usually same value)
        code = mapping.get(legacy_value, legacy_value)
        
        # Find the document type by code
        doc_type = DocType.get_type_by_code(code)
        
        if doc_type:
            try:
                doc.write({'document_type_id': doc_type.id})
                migrated += 1
            except Exception as e:
                _logger.warning(
                    "Failed to migrate document %s (type=%s): %s",
                    doc.id, legacy_value, str(e)
                )
                errors += 1
        else:
            _logger.warning(
                "No document type found for code '%s' (doc ID=%s)",
                code, doc.id
            )
            errors += 1
    
    _logger.info(
        "Document type migration complete: %d migrated, %d errors",
        migrated, errors
    )
