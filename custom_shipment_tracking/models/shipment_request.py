# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShipmentRequest(models.Model):
    """Demande d'expédition - Shipment Request for air and sea transport."""

    _name = 'shipment.request'
    _description = 'Demande d\'expédition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # region Fields
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default='Nouveau',
        tracking=True,
    )
    sale_order_ids = fields.Many2many(
        comodel_name='sale.order',
        relation='shipment_request_sale_order_rel',
        column1='shipment_request_id',
        column2='sale_order_id',
        string='Commandes liées',
        help='Commandes client confirmées liées à cette expédition',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        required=True,
        tracking=True,
        index=True,
    )
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string='Adresse de livraison',
        help='Adresse de destination pour la livraison',
    )
    destination_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Pays de destination',
        required=True,
        tracking=True,
    )
    destination_city = fields.Char(
        string='Ville de destination',
    )
    transport_mode = fields.Selection(
        selection=[
            ('air', 'Aérien'),
            ('sea', 'Maritime'),
        ],
        string='Mode de transport',
        required=True,
        default='air',
        tracking=True,
    )
    shipment_type = fields.Selection(
        selection=[
            ('fret', 'Fret'),
            ('groupage', 'Groupage'),
        ],
        string="Type d'expédition",
        required=True,
        default='groupage',
        tracking=True,
        help="Fret: Expédition directe avec documents requis (pas d'étape groupage).\n"
             "Groupage: Consolidation avec étape groupage, documents optionnels.",
    )
    planned_date = fields.Date(
        string='Date prévue d\'expédition',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('registered', 'Enregistré'),
            ('grouping', 'Groupage'),
            ('in_transit', 'En transit'),
            ('arrived', 'Arrivé à destination'),
            ('delivered', 'Livré'),
        ],
        string='Statut',
        default='registered',
        required=True,
        tracking=True,
        index=True,
        group_expand='_expand_states',  # Show all states in Kanban view
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
        help='Si décoché, la demande est archivée et n\'apparaît plus dans les listes.',
    )
    parcel_ids = fields.One2many(
        comodel_name='shipment.parcel',
        inverse_name='shipment_request_id',
        string='Colis',
    )
    parcel_count = fields.Integer(
        string='Nombre de colis',
        compute='_compute_parcel_count',
        store=True,
    )
    parcel_references = fields.Char(
        string='Références colis',
        compute='_compute_parcel_references',
        help='Liste des références de colis (ex: AB0001-1, AB0001-2)',
    )
    tracking_link_id = fields.Many2one(
        comodel_name='shipment.tracking.link',
        string='Lien de suivi',
        readonly=True,
        copy=False,
        compute='_compute_tracking_link_id',
        store=False,  # Don't store - always recompute to catch new links
    )
    main_parcel_number = fields.Char(
        string='Numéro principal',
        copy=False,
        readonly=True,
        help='Numéro de colis principal au format ABXXXX',
    )
    notes = fields.Text(
        string='Notes internes',
    )

    # Air transport specific fields
    air_flight_number = fields.Char(
        string='Numéro de vol',
    )
    air_departure_airport = fields.Char(
        string='Aéroport de départ',
    )
    air_arrival_airport = fields.Char(
        string='Aéroport d\'arrivée',
    )
    air_departure_datetime = fields.Datetime(
        string='Date/heure de départ',
    )

    # Sea transport specific fields
    sea_vessel_name = fields.Char(
        string='Nom du navire',
    )
    sea_departure_port = fields.Char(
        string='Port de départ',
    )
    sea_arrival_port = fields.Char(
        string='Port d\'arrivée',
    )
    sea_embarkation_date = fields.Date(
        string='Date d\'embarquement',
    )
    sea_container_number = fields.Char(
        string='Numéro de conteneur',
    )

    # Computed/Related fields
    tracking_url = fields.Char(
        string='URL de suivi',
        related='tracking_link_id.url',
        readonly=True,
    )
    
    # Proforma/Invoice fields
    proforma_invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Proforma',
        readonly=True,
        copy=False,
        domain=[('move_type', '=', 'out_invoice')],
        help='Facture proforma générée pour cette expédition',
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Facture',
        compute='_compute_invoice_from_proforma',
        store=True,
        copy=False,
        domain=[('move_type', '=', 'out_invoice')],
        help='Facture finale confirmée pour cette expédition',
    )
    proforma_state = fields.Selection(
        selection=[
            ('none', 'Aucun'),
            ('draft', 'Proforma créé'),
            ('confirmed', 'Facturé'),
        ],
        string='État Proforma',
        compute='_compute_invoice_from_proforma',
        store=True,
        copy=False,
        tracking=True,
    )
    transport_fee = fields.Float(
        string='Frais de transport',
        help='Frais de transport calculés ou manuels',
    )
    transport_fee_rate = fields.Float(
        string='Taux par kg',
        default=5.0,
        help='Taux de frais de transport par kg (pour calcul automatique)',
    )
    invoice_count = fields.Integer(
        string='Nombre de factures',
        compute='_compute_invoice_count',
    )
    total_weight = fields.Float(
        string='Poids total (kg)',
        compute='_compute_total_weight',
        store=True,
    )
    total_declared_value = fields.Float(
        string='Valeur déclarée totale',
        compute='_compute_total_declared_value',
        store=True,
    )

    # Additional fields for Mali/Sky Mali shipments
    lta_number = fields.Char(
        string='N° LTA',
        help='Numéro de Lettre de Transport Aérien',
        tracking=True,
    )
    airline_name = fields.Char(
        string='Compagnie aérienne',
        help='Nom de la compagnie aérienne (ex: Sky Mali)',
        tracking=True,
    )
    nature_colis = fields.Selection(
        selection=[
            ('documents', 'Documents'),
            ('marchandises', 'Marchandises'),
            ('denrees', 'Denrées alimentaires'),
            ('electronique', 'Électronique'),
            ('textile', 'Textile'),
            ('divers', 'Divers'),
        ],
        string='Nature du colis',
        default='marchandises',
        tracking=True,
    )
    customs_fees = fields.Float(
        string='Taxes douanières',
        help='Montant des taxes douanières applicables',
    )
    service_fees = fields.Float(
        string='Services annexes',
        help='Frais de transit, emballage et autres services',
    )

    # Document tracking
    document_ids = fields.One2many(
        comodel_name='shipment.document',
        inverse_name='shipment_request_id',
        string='Documents',
    )
    document_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_document_count',
    )
    all_docs_validated = fields.Boolean(
        string='Tous documents validés',
        compute='_compute_all_docs_validated',
        store=True,
        help='Indique si tous les documents requis sont validés',
    )
    docs_validated_count = fields.Integer(
        string='Documents validés',
        compute='_compute_all_docs_validated',
        store=True,
    )
    # endregion

    # region Computes
    @api.depends('parcel_ids')
    def _compute_parcel_count(self):
        for record in self:
            record.parcel_count = len(record.parcel_ids)

    @api.depends('parcel_ids.name')
    def _compute_parcel_references(self):
        """Compute comma-separated list of parcel references."""
        for record in self:
            refs = record.parcel_ids.mapped('name')
            record.parcel_references = ', '.join(filter(None, refs)) if refs else ''

    @api.model
    def _expand_states(self, states, domain):
        """Expand states in Kanban view based on shipment type.
        
        - Fret: No 'grouping' state (registered → in_transit → arrived → delivered)
        - Groupage: All states including 'grouping'
        
        This ensures correct columns are visible for drag-and-drop.
        """
        # Check if we're filtering by a specific shipment_type
        shipment_type = None
        for condition in domain:
            if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                if condition[0] == 'shipment_type' and condition[1] == '=':
                    shipment_type = condition[2]
                    break
        
        # Return states based on type
        if shipment_type == 'fret':
            return ['registered', 'in_transit', 'arrived', 'delivered']
        elif shipment_type == 'groupage':
            return ['registered', 'grouping', 'in_transit', 'arrived', 'delivered']
        else:
            # Default: show all states
            return [key for key, _ in self._fields['state'].selection]

    def _compute_tracking_link_id(self):
        """Get the active tracking link for this shipment."""
        for record in self:
            link = self.env['shipment.tracking.link'].search([
                ('shipment_request_id', '=', record.id),
                ('is_active', '=', True),
            ], limit=1)
            record.tracking_link_id = link.id if link else False

    @api.depends('proforma_invoice_id', 'proforma_invoice_id.state')
    def _compute_invoice_from_proforma(self):
        """Compute invoice_id and proforma_state based on proforma invoice state.
        
        This allows the user to validate the proforma via native Odoo invoice workflow
        and automatically updates the shipment fields.
        """
        for record in self:
            if not record.proforma_invoice_id:
                record.invoice_id = False
                record.proforma_state = 'none'
            elif record.proforma_invoice_id.state == 'posted':
                record.invoice_id = record.proforma_invoice_id.id
                record.proforma_state = 'confirmed'
            else:
                record.invoice_id = False
                record.proforma_state = 'draft'

    def _compute_invoice_count(self):
        """Compute the number of invoices linked to this shipment."""
        for record in self:
            count = 0
            if record.proforma_invoice_id:
                count += 1
            if record.invoice_id and record.invoice_id != record.proforma_invoice_id:
                count += 1
            record.invoice_count = count

    @api.depends('parcel_ids.weight')
    def _compute_total_weight(self):
        """Compute total weight of all parcels."""
        for record in self:
            record.total_weight = sum(record.parcel_ids.mapped('weight'))

    @api.depends('parcel_ids.declared_value', 'parcel_ids.total_value')
    def _compute_total_declared_value(self):
        """Compute total declared value of all parcels."""
        for record in self:
            # Use declared_value if set, otherwise use total_value from products
            total = 0.0
            for parcel in record.parcel_ids:
                if parcel.declared_value:
                    total += parcel.declared_value
                else:
                    total += parcel.total_value
            record.total_declared_value = total

    def _compute_document_count(self):
        """Compute the number of documents for this shipment."""
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('document_ids.state')
    def _compute_all_docs_validated(self):
        """Compute if all required documents are validated."""
        for record in self:
            docs = record.document_ids
            validated_count = len(docs.filtered(lambda d: d.state == 'validated'))
            total_count = len(docs)
            record.docs_validated_count = validated_count
            # All docs validated if there are documents and all are validated
            record.all_docs_validated = total_count > 0 and validated_count == total_count

    def _check_document_validation_complete(self):
        """Called when a document is validated to check if all are done."""
        self.ensure_one()
        if self.all_docs_validated:
            # Post a message in chatter
            self.message_post(
                body="✅ Tous les documents requis ont été validés. L'expédition est prête pour l'envoi.",
                message_type='notification',
            )
    # endregion

    # region CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('shipment.request') or 'Nouveau'
        return super().create(vals_list)
    # endregion

    # region Business Methods
    def _get_or_create_main_parcel_number(self):
        """
        Returns the main parcel number (ABXXXX) for this shipment request.
        If not yet assigned, generates a new one using ir.sequence.
        """
        self.ensure_one()
        if not self.main_parcel_number:
            self.main_parcel_number = self.env['ir.sequence'].next_by_code(
                'shipment.parcel.main.number'
            )
            _logger.info(
                'Generated main parcel number %s for shipment request %s',
                self.main_parcel_number,
                self.name,
            )
        return self.main_parcel_number

    def _set_state_with_parcels(self, new_state):
        """Set status on shipment and cascade to all its parcels, creating tracking events."""
        self.write({'state': new_state})
        # Cascade state to all parcels
        parcels = self.mapped('parcel_ids')
        parcels.write({'state': new_state})
        # Create tracking events for each parcel
        TrackingEvent = self.env['shipment.tracking.event']
        for parcel in parcels:
            TrackingEvent.create_status_event(parcel, new_state)

    def action_set_grouping(self):
        """Set status to Groupage (shipment + parcels).
        
        Only available for Groupage type shipments.
        """
        for shipment in self:
            if shipment.shipment_type == 'fret':
                raise UserError(_(
                    "Les expéditions de type Fret n'ont pas d'étape Groupage.\n"
                    "Utilisez 'Prêt pour envoi' pour passer directement en transit."
                ))
        self._set_state_with_parcels('grouping')

    def _check_all_products_packed(self):
        """Check that all ordered products are fully packed in parcels.
        
        Raises UserError if any product quantity remains unpacked.
        """
        self.ensure_one()
        
        if not self.sale_order_ids:
            return  # No orders, nothing to check
        
        # Get all physical product lines from linked orders
        order_lines = self.sale_order_ids.mapped('order_line').filtered(
            lambda l: l.product_id and l.product_id.type in ('product', 'consu')
        )
        
        if not order_lines:
            return  # No physical products to pack
        
        # Calculate total ordered quantity
        total_ordered = sum(order_lines.mapped('product_uom_qty'))
        
        # Calculate total packed quantity
        ParcelLine = self.env['shipment.parcel.line']
        parcel_lines = ParcelLine.search([
            ('parcel_id.shipment_request_id', '=', self.id),
        ])
        total_packed = sum(parcel_lines.mapped('quantity'))
        
        if total_packed < total_ordered:
            # Build detailed message with unpacked products
            unpacked_details = []
            for sol in order_lines:
                packed_qty = sum(ParcelLine.search([
                    ('sale_order_line_id', '=', sol.id),
                    ('parcel_id.shipment_request_id', '=', self.id),
                ]).mapped('quantity'))
                remaining = sol.product_uom_qty - packed_qty
                if remaining > 0:
                    unpacked_details.append(
                        f"• {sol.product_id.display_name}: {remaining:.2f} unités non emballées"
                    )
            
            details_str = '\n'.join(unpacked_details) if unpacked_details else ''
            raise UserError(
                "Tous les produits doivent être emballés dans un colis avant de passer en transit.\n\n"
                f"Produits restants à emballer:\n{details_str}"
            )

    def action_set_arrived(self):
        """Set status to Arrivé à destination (shipment + parcels)."""
        self._set_state_with_parcels('arrived')

    def action_set_delivered(self):
        """Set status to Livré (shipment + parcels)."""
        self._set_state_with_parcels('delivered')

    def action_generate_tracking_link(self):
        """Generate a tracking link for this shipment."""
        self.ensure_one()
        if not self.parcel_ids:
            from odoo.exceptions import UserError
            raise UserError('Aucun colis associé à cette expédition. Créez d\'abord des colis.')

        TrackingLink = self.env['shipment.tracking.link']

        # Check if shipment already has an active tracking link
        existing = TrackingLink.search([
            ('shipment_request_id', '=', self.id),
            ('is_active', '=', True),
        ], limit=1)

        if existing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': f'Cette expédition {self.name} a déjà un lien de suivi actif.',
                    'type': 'info',
                    'sticky': False,
                    'links': [{
                        'label': 'Voir le lien',
                        'url': f'/web#id={existing.id}&model=shipment.tracking.link&view_type=form',
                    }],
                }
            }

        # Create link for this shipment
        link = TrackingLink.create({'shipment_request_id': self.id})
        _logger.info(
            'Generated tracking link %s for shipment %s',
            link.token,
            self.name,
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.tracking.link',
            'view_mode': 'form',
            'res_id': link.id,
            'name': 'Lien de suivi généré',
            'target': 'new',
        }

    # region Proforma / Invoice Methods
    def _get_transport_product(self):
        """Get or create the transport service product for invoicing."""
        # Try to get the transport product by XML ID using env.ref
        try:
            transport_product = self.env.ref(
                'custom_shipment_tracking.product_transport_service', raise_if_not_found=False
            )
            if transport_product:
                return transport_product
        except Exception:
            pass

        # Search by default_code as fallback
        Product = self.env['product.product']
        transport_product = Product.search([
            ('default_code', '=', 'TRANSPORT_SERVICE'),
        ], limit=1)

        if not transport_product:
            transport_product = Product.create({
                'name': 'Service de Transport',
                'default_code': 'TRANSPORT_SERVICE',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': 0.0,
                'description_sale': 'Frais de transport',
            })
            _logger.info('Created transport service product: %s', transport_product.name)

        return transport_product

    def _calculate_transport_fee(self):
        """Calculate transport fee based on total weight and rate."""
        self.ensure_one()
        return self.total_weight * self.transport_fee_rate

    def _prepare_proforma_lines(self):
        """Prepare invoice lines for the proforma.
        
        Returns a list of invoice line vals including:
        - One line per main_number (grouping all parcels with same main_number)
        - One line for transport fees
        - One line for customs fees (if any)
        - One line for service fees (if any)
        """
        self.ensure_one()
        lines = []

        # Group parcels by main_number
        parcels_by_main_number = {}
        for parcel in self.parcel_ids:
            main_num = parcel.main_number or 'N/A'
            if main_num not in parcels_by_main_number:
                parcels_by_main_number[main_num] = {
                    'parcels': self.env['shipment.parcel'],
                    'total_weight': 0.0,
                    'total_value': 0.0,
                }
            parcels_by_main_number[main_num]['parcels'] |= parcel
            parcels_by_main_number[main_num]['total_weight'] += parcel.weight
            # Use declared value or total_value
            parcel_value = parcel.declared_value if parcel.declared_value else parcel.total_value
            parcels_by_main_number[main_num]['total_value'] += parcel_value

        # Create one line per main_number group
        for main_num, data in parcels_by_main_number.items():
            parcel_count = len(data['parcels'])
            total_weight = data['total_weight']
            total_value = data['total_value']
            
            # Build description with parcel count
            if parcel_count == 1:
                description = f"Colis {main_num} ({total_weight:.2f} kg)"
            else:
                description = f"Colis {main_num} - {parcel_count} colis ({total_weight:.2f} kg total)"
            
            lines.append({
                'name': description,
                'quantity': parcel_count,
                'price_unit': total_value / parcel_count if parcel_count > 0 else 0.0,
            })

        # Add transport fee line
        transport_fee = self._calculate_transport_fee()
        if transport_fee > 0:
            transport_product = self._get_transport_product()
            lines.append({
                'product_id': transport_product.id,
                'name': f"Frais de transport ({self.total_weight:.2f} kg x {self.transport_fee_rate:.2f} / kg)",
                'quantity': 1,
                'price_unit': transport_fee,
            })
            self.transport_fee = transport_fee

        # Add customs fees line (if any)
        if self.customs_fees > 0:
            lines.append({
                'name': 'Taxes douanieres',
                'quantity': 1,
                'price_unit': self.customs_fees,
            })

        # Add service fees line (if any)
        if self.service_fees > 0:
            lines.append({
                'name': 'Services annexes (transit, emballage)',
                'quantity': 1,
                'price_unit': self.service_fees,
            })

        return lines

    def action_create_proforma(self):
        """Create a proforma invoice (draft) for this shipment."""
        self.ensure_one()

        if self.proforma_invoice_id:
            raise UserError("Un proforma existe déjà pour cette expédition.")

        if not self.parcel_ids:
            raise UserError("Aucun colis n'est associé à cette expédition.")

        if not self.partner_id:
            raise UserError("Veuillez définir un client pour cette expédition.")

        # Prepare invoice vals
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'ref': f"Proforma - {self.name}",
            'narration': f"Expédition: {self.name}\nNuméro principal colis: {self.main_parcel_number or 'N/A'}",
            'invoice_line_ids': [(0, 0, line) for line in self._prepare_proforma_lines()],
        }

        # Create the invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Link invoice to shipment (proforma_state will be computed automatically)
        self.write({
            'proforma_invoice_id': invoice.id,
        })

        _logger.info(
            'Created proforma invoice %s for shipment %s',
            invoice.name,
            self.name,
        )

        # Return action to view the created proforma
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_confirm_and_invoice(self):
        """Confirm the proforma and convert it to a final invoice.
        
        Note: This method is kept for backwards compatibility but the button
        has been removed from the UI. Users should validate the invoice via
        the native Odoo invoice workflow (Factures smart button).
        """
        self.ensure_one()

        if not self.proforma_invoice_id:
            raise UserError("Aucun proforma n'existe pour cette expédition. Créez d'abord un proforma.")

        # If invoice is already posted, just return
        if self.proforma_invoice_id.state == 'posted':
            raise UserError("La facture a déjà été confirmée.")

        if self.proforma_invoice_id.state != 'draft':
            raise UserError("Le proforma doit être à l'état brouillon pour être confirmé.")

        # Post the invoice to confirm it
        # The computed fields (invoice_id, proforma_state) will update automatically
        self.proforma_invoice_id.action_post()

        _logger.info(
            'Confirmed invoice %s for shipment %s',
            self.proforma_invoice_id.name,
            self.name,
        )

        # Return action to view the confirmed invoice
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.proforma_invoice_id.id,
            'target': 'current',
        }

    def action_view_invoices(self):
        """Open invoices related to this shipment."""
        self.ensure_one()
        
        invoice_ids = []
        if self.proforma_invoice_id:
            invoice_ids.append(self.proforma_invoice_id.id)
        if self.invoice_id and self.invoice_id.id not in invoice_ids:
            invoice_ids.append(self.invoice_id.id)

        if not invoice_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Information',
                    'message': 'Aucune facture associée à cette expédition.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        if len(invoice_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice_ids[0],
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoice_ids)],
            'name': 'Factures',
            'target': 'current',
        }

    # region Document Methods
    def action_generate_documents(self):
        """Generate all required documents for this shipment."""
        self.ensure_one()
        
        if self.document_ids:
            raise UserError("Les documents ont déjà été générés pour cette expédition.")
        
        Document = self.env['shipment.document']
        document_types = ['fdi', 'dcvi', 'declaration', 'lta']
        
        created_docs = self.env['shipment.document']
        for doc_type in document_types:
            doc = Document.create({
                'shipment_request_id': self.id,
                'document_type': doc_type,
                'responsible_id': self.env.user.id,
            })
            created_docs |= doc
        
        _logger.info(
            'Generated %d documents for shipment %s',
            len(created_docs),
            self.name,
        )
        
        self.message_post(
            body=f"📄 {len(created_docs)} documents générés: FDI, DCVI, Déclaration de contenu, N° LTA",
            message_type='notification',
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents générés',
            'res_model': 'shipment.document',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', created_docs.ids)],
            'target': 'current',
        }

    def action_view_documents(self):
        """Open documents related to this shipment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents - {self.name}',
            'res_model': 'shipment.document',
            'view_mode': 'kanban,list,form',
            'domain': [('shipment_request_id', '=', self.id)],
            'context': {'default_shipment_request_id': self.id},
            'target': 'current',
        }

    def action_open_bulk_create_wizard(self):
        """Open wizard to bulk create parcels."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Creer colis en masse',
            'res_model': 'parcel.bulk.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shipment_request_id': self.id,
            },
        }

    def action_ready_for_transit(self):
        """Set shipment to in_transit after all validations pass.
        
        This is the 'Prêt pour envoi' button that validates based on shipment type:
        
        Fret workflow (from 'registered'):
        - All products must be packed
        - Invoice must be confirmed
        - All documents must be validated (REQUIRED)
        
        Groupage workflow (from 'grouping'):
        - All products must be packed
        - Invoice must be confirmed
        - Documents NOT required
        """
        for shipment in self:
            # Check products are packed
            shipment._check_all_products_packed()
            
            # Check invoice is confirmed
            if shipment.proforma_state != 'confirmed':
                raise UserError(_(
                    "La facture doit être confirmée avant de pouvoir envoyer l'expédition.\n"
                    "Créez d'abord un proforma puis confirmez-le."
                ))
            
            # Document validation depends on shipment type
            if shipment.shipment_type == 'fret':
                # Fret: Documents ARE required
                if not shipment.all_docs_validated:
                    missing_docs = shipment.document_ids.filtered(lambda d: d.state != 'validated')
                    if missing_docs:
                        doc_names = ', '.join(missing_docs.mapped('name'))
                        raise UserError(_(
                            "Type Fret: Tous les documents doivent être validés avant l'envoi.\n\n"
                            "Documents non validés:\n%s"
                        ) % doc_names)
                    else:
                        raise UserError(_(
                            "Type Fret: Aucun document n'a été généré pour cette expédition.\n"
                            "Cliquez sur 'Générer Documents' pour créer les documents requis."
                        ))
            # Groupage: Documents NOT required - skip validation
        
        # All checks passed, set to in_transit
        self._set_state_with_parcels('in_transit')
        
        for shipment in self:
            if shipment.shipment_type == 'fret':
                shipment.message_post(
                    body="🚀 Expédition Fret prête pour envoi - Documents validés, facture confirmée.",
                    message_type='notification',
                )
            else:
                shipment.message_post(
                    body="🚀 Expédition Groupage prête pour envoi - Facture confirmée.",
                    message_type='notification',
                )
    # endregion

    # region CRUD Overrides
    def write(self, vals):
        """Override write to handle Kanban drag-drop state changes.
        
        When state changes via Kanban drag-drop:
        - Validates transitions based on shipment type (Fret vs Groupage)
        - Syncs parcel status with shipment status
        
        Fret workflow: registered → in_transit (documents required)
        Groupage workflow: grouping → in_transit (documents NOT required)
        """
        # Check if state is being changed
        if 'state' in vals:
            new_state = vals['state']
            for shipment in self:
                old_state = shipment.state
                
                # Block invalid state transitions based on type
                if shipment.shipment_type == 'fret' and new_state == 'grouping':
                    raise UserError(_(
                        "⚠️ Les expéditions de type Fret n'ont pas d'étape Groupage.\n"
                        "Passez directement de 'Enregistré' à 'En transit'."
                    ))
                
                # Validate transition TO in_transit
                if new_state == 'in_transit':
                    # Check invoice is confirmed (both types)
                    if shipment.proforma_state != 'confirmed':
                        raise UserError(_(
                            "⚠️ Impossible de passer en transit !\n\n"
                            "La facture doit être confirmée avant de pouvoir envoyer l'expédition.\n"
                            "Créez d'abord un proforma puis confirmez-le."
                        ))
                    
                    # Document validation depends on type
                    if shipment.shipment_type == 'fret':
                        # Fret: Documents ARE required
                        if not shipment.all_docs_validated:
                            missing_docs = shipment.document_ids.filtered(lambda d: d.state != 'validated')
                            if missing_docs:
                                doc_names = ', '.join(missing_docs.mapped('name'))
                                raise UserError(_(
                                    "⚠️ Impossible de passer en transit !\n\n"
                                    "Type Fret: Tous les documents doivent être validés avant l'envoi.\n\n"
                                    "Documents non validés:\n%s"
                                ) % doc_names)
                            else:
                                raise UserError(_(
                                    "⚠️ Impossible de passer en transit !\n\n"
                                    "Type Fret: Aucun document n'a été généré pour cette expédition.\n"
                                    "Cliquez sur 'Générer Documents' pour créer les documents requis."
                                ))
                    # Groupage: Documents NOT required - no validation
        
        # Perform the write
        result = super().write(vals)
        
        # If state changed, sync parcels
        if 'state' in vals:
            new_state = vals['state']
            # Cascade state to all parcels
            parcels = self.mapped('parcel_ids')
            if parcels:
                parcels.write({'state': new_state})
                # Create tracking events for each parcel
                TrackingEvent = self.env['shipment.tracking.event']
                for parcel in parcels:
                    TrackingEvent.create_status_event(parcel, new_state)
        
        return result
    # endregion
    # endregion
    # endregion


class SaleOrderShipmentExtension(models.Model):
    """Extension to sale.order to support automatic shipment request creation."""

    _inherit = 'sale.order'

    shipment_request_ids = fields.Many2many(
        comodel_name='shipment.request',
        relation='shipment_request_sale_order_rel',
        column1='sale_order_id',
        column2='shipment_request_id',
        string='Demandes d\'expédition',
    )
    shipment_request_count = fields.Integer(
        string='Nombre d\'expéditions',
        compute='_compute_shipment_request_count',
    )

    @api.depends('shipment_request_ids')
    def _compute_shipment_request_count(self):
        for order in self:
            order.shipment_request_count = len(order.shipment_request_ids)

    def action_confirm(self):
        """Override to create shipment request on CRM-originated order confirmation.
        
        Also sets the CRM opportunity to 'Won' stage when order is confirmed.
        Validates that the customer has complete address information for shipment creation.
        """
        # Validate address completeness for shipment creation
        for order in self:
            if order.opportunity_id:
                order._validate_partner_address_for_shipment()
        
        res = super().action_confirm()
        for order in self:
            # Check if order originates from CRM (has opportunity_id)
            if order.opportunity_id:
                # Create shipment request if not exists
                if not order.shipment_request_ids:
                    order._create_shipment_request_from_order()
                
                # Set opportunity to Won stage
                order._set_opportunity_won()
        return res

    def _validate_partner_address_for_shipment(self, require_opportunity=True):
        """Validate that partner has complete address for shipment creation.
        
        Args:
            require_opportunity: If True (default), only validates for CRM orders.
                               If False, always validates (for manual creation).
        
        Raises UserError if address is incomplete.
        """
        self.ensure_one()
        
        # Skip validation if require_opportunity=True and no opportunity linked
        # (backwards compatibility with CRM-only auto-creation)
        if require_opportunity and not self.opportunity_id:
            return
        
        # Use shipping address if available, otherwise billing address
        partner = self.partner_shipping_id or self.partner_id
        if not partner:
            return
        
        missing_fields = []
        field_labels = {
            'street': 'Adresse (Rue)',
            'city': 'Ville',
            'zip': 'Code postal',
            'country_id': 'Pays',
        }
        
        for field_name, label in field_labels.items():
            if not getattr(partner, field_name):
                missing_fields.append(label)
        
        if missing_fields:
            raise UserError(_(
                "Impossible de créer la demande d'expédition. "
                "Les informations d'adresse du client sont incomplètes.\n\n"
                "Client: %(partner_name)s\n"
                "Champs manquants:\n%(missing)s\n\n"
                "Veuillez compléter les informations d'adresse du client."
            ) % {
                'partner_name': partner.display_name,
                'missing': '\n'.join(f'  • {f}' for f in missing_fields),
            })

    def _set_opportunity_won(self):
        """Set the linked CRM opportunity to 'Won' stage."""
        self.ensure_one()
        if not self.opportunity_id:
            return
        
        # Find Won stage (crm.stage_lead4)
        won_stage = self.env.ref('crm.stage_lead4', raise_if_not_found=False)
        if not won_stage:
            # Fallback: search for stage with is_won=True
            won_stage = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        
        if won_stage and self.opportunity_id.stage_id != won_stage:
            self.opportunity_id.write({'stage_id': won_stage.id})
            _logger.info(
                'Set opportunity %s to Won stage after order %s confirmation',
                self.opportunity_id.name,
                self.name,
            )

    def _create_shipment_request_from_order(self):
        """Create a shipment request linked to this confirmed order."""
        self.ensure_one()
        ShipmentRequest = self.env['shipment.request']

        vals = {
            'sale_order_ids': [(4, self.id)],
            'partner_id': self.partner_id.id,
            'partner_shipping_id': self.partner_shipping_id.id if self.partner_shipping_id else False,
            'destination_country_id': (
                self.partner_shipping_id.country_id.id
                if self.partner_shipping_id and self.partner_shipping_id.country_id
                else self.partner_id.country_id.id
                if self.partner_id.country_id
                else False
            ),
            'destination_city': (
                self.partner_shipping_id.city
                if self.partner_shipping_id
                else self.partner_id.city
            ),
            'company_id': self.company_id.id,
        }

        # Validate required fields
        if not vals.get('destination_country_id'):
            _logger.warning(
                'Cannot auto-create shipment request for order %s: missing destination country',
                self.name,
            )
            return False

        shipment = ShipmentRequest.create(vals)
        _logger.info(
            'Auto-created shipment request %s from order %s',
            shipment.name,
            self.name,
        )
        return shipment

    def _amount_to_text(self, amount):
        """Convert amount to French text (ex: 493800 -> 'Quatre cent quatre-vingt-treize mille huit cent Francs CFA').
        
        This is a simplified French number to text converter for amounts.
        Used by the proforma invoice PDF report.
        """
        if amount == 0:
            return "Zero Francs CFA"
        
        # Get currency name from company
        currency_name = self.company_id.currency_id.name or 'Francs CFA'
        if currency_name in ('XOF', 'XAF'):
            currency_name = 'Francs CFA'
        elif currency_name == 'EUR':
            currency_name = 'Euros'
        elif currency_name == 'USD':
            currency_name = 'Dollars US'
        
        # French number words
        units = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf',
                 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize', 'dix-sept',
                 'dix-huit', 'dix-neuf']
        tens = ['', 'dix', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 
                'soixante', 'quatre-vingt', 'quatre-vingt']
        
        def _convert_less_than_hundred(n):
            """Convert number less than 100 to French text."""
            if n < 20:
                return units[n]
            elif n < 70:
                ten = n // 10
                unit = n % 10
                if unit == 0:
                    return tens[ten]
                elif unit == 1 and ten != 8:
                    return f"{tens[ten]} et un"
                else:
                    return f"{tens[ten]}-{units[unit]}"
            elif n < 80:
                # 70-79: soixante-dix, soixante-onze, etc.
                unit = n - 60
                if unit == 11:
                    return "soixante et onze"
                return f"soixante-{units[unit]}"
            else:
                # 80-99: quatre-vingt, quatre-vingt-un, etc.
                unit = n - 80
                if unit == 0:
                    return "quatre-vingts"
                return f"quatre-vingt-{units[unit]}"
        
        def _convert_less_than_thousand(n):
            """Convert number less than 1000 to French text."""
            if n < 100:
                return _convert_less_than_hundred(n)
            else:
                hundreds = n // 100
                remainder = n % 100
                if hundreds == 1:
                    prefix = "cent"
                else:
                    prefix = f"{units[hundreds]} cent"
                
                if remainder == 0:
                    if hundreds > 1:
                        return f"{units[hundreds]} cents"
                    return "cent"
                else:
                    return f"{prefix} {_convert_less_than_hundred(remainder)}"
        
        def _convert(n):
            """Convert any positive integer to French text."""
            if n < 1000:
                return _convert_less_than_thousand(n)
            elif n < 1000000:
                thousands = n // 1000
                remainder = n % 1000
                if thousands == 1:
                    prefix = "mille"
                else:
                    prefix = f"{_convert_less_than_thousand(thousands)} mille"
                
                if remainder == 0:
                    return prefix
                else:
                    return f"{prefix} {_convert_less_than_thousand(remainder)}"
            elif n < 1000000000:
                millions = n // 1000000
                remainder = n % 1000000
                if millions == 1:
                    prefix = "un million"
                else:
                    prefix = f"{_convert_less_than_thousand(millions)} millions"
                
                if remainder == 0:
                    return prefix
                else:
                    return f"{prefix} {_convert(remainder)}"
            else:
                # Milliards (billions in French)
                milliards = n // 1000000000
                remainder = n % 1000000000
                if milliards == 1:
                    prefix = "un milliard"
                else:
                    prefix = f"{_convert_less_than_thousand(milliards)} milliards"
                
                if remainder == 0:
                    return prefix
                else:
                    return f"{prefix} {_convert(remainder)}"
        
        # Convert amount (integer part only)
        int_amount = int(round(amount))
        text = _convert(int_amount)
        
        # Capitalize first letter and add currency
        if text:
            text = text[0].upper() + text[1:]
        
        return f"{text} {currency_name}"

    def action_view_shipment_requests(self):
        """Open shipment requests linked to this order."""
        self.ensure_one()
        
        if self.shipment_request_count == 1:
            # Open directly in form view for single shipment
            return {
                'type': 'ir.actions.act_window',
                'name': 'Expédition',
                'res_model': 'shipment.request',
                'view_mode': 'form',
                'res_id': self.shipment_request_ids.id,
                'target': 'current',
            }
        else:
            # Open list view for multiple shipments
            return {
                'type': 'ir.actions.act_window',
                'name': 'Expéditions',
                'res_model': 'shipment.request',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.shipment_request_ids.ids)],
                'target': 'current',
            }

    def action_create_shipment_request(self):
        """Manually create a shipment request from this sale order.
        
        This action allows creating shipment requests directly from confirmed
        sale orders WITHOUT requiring a CRM opportunity. This is useful for
        orders created directly in the Sales module.
        """
        self.ensure_one()
        
        # Check order is confirmed
        if self.state != 'sale':
            raise UserError(_(
                "Impossible de créer une expédition pour une commande non confirmée.\n"
                "Veuillez d'abord confirmer la commande."
            ))
        
        # Check no shipment exists already
        if self.shipment_request_ids:
            raise UserError(_(
                "Une demande d'expédition existe déjà pour cette commande.\n"
                "Utilisez le bouton 'Expéditions' pour la consulter."
            ))
        
        # Validate partner address
        self._validate_partner_address_for_shipment(require_opportunity=False)
        
        # Create shipment request
        shipment = self._create_shipment_request_from_order()
        
        if not shipment:
            raise UserError(_(
                "Impossible de créer la demande d'expédition.\n"
                "Vérifiez que le pays de destination est renseigné dans l'adresse du client."
            ))
        
        # Return action to view the created shipment
        return {
            'type': 'ir.actions.act_window',
            'name': _('Demande d\'expédition créée'),
            'res_model': 'shipment.request',
            'view_mode': 'form',
            'res_id': shipment.id,
            'target': 'current',
        }


class CrmLeadShipmentExtension(models.Model):
    """Extend CRM Lead to warn when moving to Proposition without quotation."""

    _inherit = 'crm.lead'

    def write(self, vals):
        """Override to warn when moving to Proposition stage without quotation."""
        res = super().write(vals)
        
        # Check if stage is being changed to Proposition
        if 'stage_id' in vals:
            proposition_stage = self.env.ref('crm.stage_lead3', raise_if_not_found=False)
            if proposition_stage and vals.get('stage_id') == proposition_stage.id:
                for lead in self:
                    # Check if any quotation exists for this opportunity
                    existing_orders = self.env['sale.order'].search([
                        ('opportunity_id', '=', lead.id),
                    ], limit=1)
                    
                    if not existing_orders:
                        # Send warning notification via bus
                        lead._notify_no_quotation_warning()
        
        return res

    def _notify_no_quotation_warning(self):
        """Send warning notification when no quotation attached."""
        self.ensure_one()
        
        # Post a notification to the user via bus
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'title': "⚠️ Attention",
                'message': f"L'opportunité '{self.name}' passe en étape Proposition sans devis attaché.",
                'type': 'warning',
                'sticky': True,
            }
        )
        
        _logger.warning(
            'Opportunity %s moved to Proposition without quotation',
            self.name,
        )
