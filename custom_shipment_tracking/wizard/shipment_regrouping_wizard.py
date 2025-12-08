# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShipmentRegroupingWizard(models.TransientModel):
    """Wizard to merge multiple compatible shipment requests into a single one."""

    _name = 'shipment.regrouping.wizard'
    _description = 'Assistant de regroupement des expéditions'

    # region Fields
    shipment_ids = fields.Many2many(
        comodel_name='shipment.request',
        relation='shipment_regrouping_wizard_request_rel',
        column1='wizard_id',
        column2='shipment_id',
        string='Demandes sélectionnées',
        readonly=True,
    )
    master_shipment_id = fields.Many2one(
        comodel_name='shipment.request',
        string='Demande principale',
        domain="[('id', 'in', shipment_ids)]",
        help='La demande qui recevra tous les colis des autres demandes',
    )
    compatible_count = fields.Integer(
        string='Demandes compatibles',
        compute='_compute_compatibility',
    )
    incompatible_warning = fields.Text(
        string='Avertissement d\'incompatibilité',
        compute='_compute_compatibility',
    )
    is_compatible = fields.Boolean(
        string='Compatible',
        compute='_compute_compatibility',
    )
    total_parcels = fields.Integer(
        string='Total colis',
        compute='_compute_totals',
    )
    total_weight = fields.Float(
        string='Poids total (kg)',
        compute='_compute_totals',
    )
    # endregion

    # region Default Get
    @api.model
    def default_get(self, fields_list):
        """Populate shipment_ids from active_ids context."""
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')

        if active_model != 'shipment.request' or not active_ids:
            return res

        shipments = self.env['shipment.request'].browse(active_ids).exists()
        if not shipments:
            return res

        res['shipment_ids'] = [(6, 0, shipments.ids)]

        # Pre-select master as the first shipment (oldest by ID)
        if len(shipments) >= 1:
            res['master_shipment_id'] = min(shipments.ids)

        return res
    # endregion

    # region Computed Fields
    @api.depends('shipment_ids')
    def _compute_compatibility(self):
        """Check compatibility of selected shipment requests."""
        for wizard in self:
            shipments = wizard.shipment_ids
            warnings = []
            compatible_count = 0

            if len(shipments) < 2:
                wizard.incompatible_warning = _('Vous devez sélectionner au moins 2 demandes à regrouper.')
                wizard.compatible_count = 0
                wizard.is_compatible = False
                continue

            # Reference values from first shipment
            ref_shipment = shipments[0]
            ref_partner = ref_shipment.partner_id
            ref_transport_mode = ref_shipment.transport_mode
            ref_destination = ref_shipment.destination_country_id

            incompatible_shipments = []

            for shipment in shipments:
                issues = []

                # Check status
                if shipment.state != 'registered':
                    issues.append(_('statut "%s" (requis: "Enregistré")') % dict(
                        shipment._fields['state'].selection
                    ).get(shipment.state, shipment.state))

                # Check partner
                if shipment.partner_id != ref_partner:
                    issues.append(_('client "%s" (différent de "%s")') % (
                        shipment.partner_id.name,
                        ref_partner.name,
                    ))

                # Check transport mode
                if shipment.transport_mode != ref_transport_mode:
                    mode_labels = dict(shipment._fields['transport_mode'].selection)
                    issues.append(_('mode de transport "%s" (différent de "%s")') % (
                        mode_labels.get(shipment.transport_mode, shipment.transport_mode),
                        mode_labels.get(ref_transport_mode, ref_transport_mode),
                    ))

                # Check destination country
                if shipment.destination_country_id != ref_destination:
                    issues.append(_('pays de destination "%s" (différent de "%s")') % (
                        shipment.destination_country_id.name or _('Non défini'),
                        ref_destination.name or _('Non défini'),
                    ))

                if issues:
                    incompatible_shipments.append({
                        'shipment': shipment,
                        'issues': issues,
                    })
                else:
                    compatible_count += 1

            # Build warning message
            if incompatible_shipments:
                warning_lines = [_('Attention: les demandes suivantes ne sont pas compatibles:')]
                for item in incompatible_shipments:
                    issue_text = ', '.join(item['issues'])
                    warning_lines.append(f'• {item["shipment"].name}: {issue_text}')
                wizard.incompatible_warning = '\n'.join(warning_lines)
                wizard.is_compatible = False
            else:
                wizard.incompatible_warning = False
                wizard.is_compatible = True

            wizard.compatible_count = compatible_count

    @api.depends('shipment_ids')
    def _compute_totals(self):
        """Compute total parcels and weight across all selected shipments."""
        for wizard in self:
            parcels = wizard.shipment_ids.mapped('parcel_ids')
            wizard.total_parcels = len(parcels)
            wizard.total_weight = sum(parcels.mapped('weight'))
    # endregion

    # region Validation
    def _validate_regrouping(self):
        """Validate that regrouping can proceed. Raises UserError if not."""
        self.ensure_one()

        # Check minimum selection
        if len(self.shipment_ids) < 2:
            raise UserError(_(
                'Vous devez sélectionner au moins 2 demandes d\'expédition pour effectuer un regroupement.'
            ))

        # Check master selection
        if not self.master_shipment_id:
            raise UserError(_(
                'Veuillez sélectionner la demande principale qui recevra les colis.'
            ))

        # Check master is in selected shipments
        if self.master_shipment_id not in self.shipment_ids:
            raise UserError(_(
                'La demande principale doit faire partie des demandes sélectionnées.'
            ))

        # Reference values
        ref_partner = self.master_shipment_id.partner_id
        ref_transport_mode = self.master_shipment_id.transport_mode
        ref_destination = self.master_shipment_id.destination_country_id

        # Validate all shipments
        for shipment in self.shipment_ids:
            # Check status
            if shipment.state != 'registered':
                state_label = dict(shipment._fields['state'].selection).get(
                    shipment.state, shipment.state
                )
                raise UserError(_(
                    'La demande "%s" est au statut "%s". '
                    'Seules les demandes au statut "Enregistré" peuvent être regroupées.'
                ) % (shipment.name, state_label))

            # Check partner
            if shipment.partner_id != ref_partner:
                raise UserError(_(
                    'La demande "%s" appartient au client "%s", '
                    'différent du client de la demande principale "%s". '
                    'Toutes les demandes doivent avoir le même client.'
                ) % (shipment.name, shipment.partner_id.name, ref_partner.name))

            # Check transport mode
            if shipment.transport_mode != ref_transport_mode:
                mode_labels = dict(shipment._fields['transport_mode'].selection)
                raise UserError(_(
                    'La demande "%s" utilise le mode de transport "%s", '
                    'différent du mode "%s" de la demande principale. '
                    'Toutes les demandes doivent avoir le même mode de transport.'
                ) % (
                    shipment.name,
                    mode_labels.get(shipment.transport_mode, shipment.transport_mode),
                    mode_labels.get(ref_transport_mode, ref_transport_mode),
                ))

            # Check destination country
            if shipment.destination_country_id != ref_destination:
                raise UserError(_(
                    'La demande "%s" a pour destination "%s", '
                    'différent de la destination "%s" de la demande principale. '
                    'Toutes les demandes doivent avoir le même pays de destination.'
                ) % (
                    shipment.name,
                    shipment.destination_country_id.name or _('Non défini'),
                    ref_destination.name or _('Non défini'),
                ))

        return True
    # endregion

    # region Actions
    def action_regroup(self):
        """Perform the merge of selected shipment requests into the master."""
        self.ensure_one()
        self._validate_regrouping()

        master = self.master_shipment_id
        other_shipments = self.shipment_ids - master

        if not other_shipments:
            raise UserError(_('Il n\'y a pas d\'autres demandes à regrouper avec la demande principale.'))

        # Collect info for chatter message
        merged_names = other_shipments.mapped('name')
        merged_parcel_count = sum(other_shipments.mapped('parcel_count'))
        merged_sale_orders = other_shipments.mapped('sale_order_ids')

        # Move parcels from other shipments to master
        parcels_to_move = other_shipments.mapped('parcel_ids')
        if parcels_to_move:
            # Get the current max sequence on master
            existing_parcels = master.parcel_ids
            max_sequence = max(existing_parcels.mapped('sequence')) if existing_parcels else 0

            # Reassign parcels to master with new sequences
            for parcel in parcels_to_move:
                max_sequence += 1
                parcel.write({
                    'shipment_request_id': master.id,
                    'main_number': master._get_or_create_main_parcel_number(),
                    'sequence': max_sequence,
                })
                _logger.info(
                    'Moved parcel %s to master shipment %s with new sequence %d',
                    parcel.name,
                    master.name,
                    max_sequence,
                )

        # Link sale orders from other shipments to master
        if merged_sale_orders:
            master.write({
                'sale_order_ids': [(4, so.id) for so in merged_sale_orders],
            })

        # Archive other shipments
        other_shipments.write({'active': False})

        # Post chatter message on master
        message_body = _(
            '<p><strong>Regroupement effectué</strong></p>'
            '<p>Les demandes suivantes ont été fusionnées dans cette demande:</p>'
            '<ul>%s</ul>'
            '<p>Nombre de colis transférés: <strong>%d</strong></p>'
        ) % (
            ''.join(f'<li>{name}</li>' for name in merged_names),
            merged_parcel_count,
        )
        master.message_post(body=message_body, message_type='comment')

        # Post chatter message on archived shipments
        archive_message = _(
            '<p>Cette demande a été archivée suite à un regroupement.</p>'
            '<p>Les colis ont été transférés vers la demande: <strong>%s</strong></p>'
        ) % master.name

        # Temporarily activate to post message, then re-archive
        for shipment in other_shipments.with_context(active_test=False):
            shipment.with_context(mail_create_nosubscribe=True).message_post(
                body=archive_message,
                message_type='comment',
            )

        _logger.info(
            'Regrouped %d shipments into master %s: %s',
            len(other_shipments),
            master.name,
            ', '.join(merged_names),
        )

        # Return action to view the master shipment
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipment.request',
            'res_id': master.id,
            'view_mode': 'form',
            'target': 'current',
            'name': master.name,
        }
    # endregion
