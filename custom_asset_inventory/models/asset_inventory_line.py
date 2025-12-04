# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Model: asset.inventory.line
============================

Ligne d'inventaire des immobilisations.

Ce modèle représente une ligne d'inventaire liée à un PRODUIT (équipement physique)
qui peut avoir une immobilisation comptable associée pour la valorisation.

Workflow:
1. L'utilisateur sélectionne un PRODUIT à inventorier
2. Si le produit a une immobilisation liée, les valeurs financières sont calculées
3. L'utilisateur renseigne l'état physique (présent, manquant, dégradé, à réparer)
4. Les rapports utilisent les données financières de l'immobilisation
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AssetInventoryLine(models.Model):
    """Ligne d'inventaire d'une immobilisation."""

    _name = 'asset.inventory.line'
    _description = "Ligne d'inventaire immobilisation"
    _order = 'campaign_id, product_id'
    _rec_name = 'display_name'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    # Relation avec la campagne
    campaign_id = fields.Many2one(
        comodel_name='asset.inventory.campaign',
        string="Campagne",
        required=True,
        ondelete='cascade',
        index=True,
        help="Campagne d'inventaire à laquelle appartient cette ligne",
    )
    
    # Relation avec le PRODUIT (sélection principale par l'utilisateur)
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Produit",
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('company_id', 'in', [company_id, False])]",
        help="Produit/équipement à inventorier",
    )
    
    # Relation avec l'immobilisation comptable (liée au produit ou sélection manuelle)
    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string="Immobilisation",
        compute='_compute_asset_id',
        store=True,
        readonly=False,
        ondelete='set null',
        index=True,
        domain="[('company_id', '=', company_id)]",
        help="Immobilisation comptable liée au produit (ou sélection manuelle)",
    )
    
    # Nom d'affichage
    display_name = fields.Char(
        string="Nom",
        compute='_compute_display_name',
        store=True,
    )
    
    # État physique
    physical_status = fields.Selection(
        selection=[
            ('present', 'Présent'),
            ('missing', 'Manquant'),
            ('degraded', 'Dégradé'),
            ('to_repair', 'À réparer'),
        ],
        string="État physique",
        tracking=True,
        help="État physique constaté lors de l'inventaire",
    )
    
    # Localisation
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string="Emplacement",
        domain="[('company_id', 'in', [company_id, False])]",
        help="Emplacement où se trouve l'équipement",
    )
    
    # Responsable
    responsible_id = fields.Many2one(
        comodel_name='res.users',
        string="Responsable",
        default=lambda self: self.env.user,
        help="Utilisateur responsable de l'inventaire de cette ligne",
    )
    
    # Commentaires et pièces jointes
    comment = fields.Text(
        string="Commentaire",
        help="Observations et remarques sur l'état de l'équipement",
    )
    image = fields.Binary(
        string="Photo",
        attachment=True,
        help="Photo de l'équipement lors de l'inventaire",
    )
    
    # Champs related depuis la campagne
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        related='campaign_id.company_id',
        store=True,
        readonly=True,
        help="Société de la campagne d'inventaire",
    )
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Entrepôt",
        related='campaign_id.warehouse_id',
        store=True,
        readonly=True,
        help="Entrepôt de la campagne d'inventaire",
    )
    campaign_state = fields.Selection(
        related='campaign_id.state',
        string="État campagne",
        readonly=True,
    )
    
    # Informations du produit (lecture seule)
    product_name = fields.Char(
        string="Nom produit",
        related='product_id.name',
        readonly=True,
    )
    product_code = fields.Char(
        string="Référence produit",
        related='product_id.default_code',
        readonly=True,
    )
    product_categ_id = fields.Many2one(
        comodel_name='product.category',
        string="Catégorie produit",
        related='product_id.categ_id',
        readonly=True,
        store=True,
    )
    
    # Informations de l'immobilisation (lecture seule)
    asset_name = fields.Char(
        string="Nom immobilisation",
        related='asset_id.name',
        readonly=True,
    )
    asset_state = fields.Selection(
        related='asset_id.state',
        string="État comptable",
        readonly=True,
    )
    asset_acquisition_date = fields.Date(
        related='asset_id.acquisition_date',
        string="Date d'acquisition",
        readonly=True,
    )
    asset_group_id = fields.Many2one(
        comodel_name='account.asset.group',
        string="Groupe d'immobilisation",
        related='asset_id.asset_group_id',
        readonly=True,
        store=True,
    )
    
    # -------------------------------------------------------------------------
    # COMPUTED FINANCIAL FIELDS
    # -------------------------------------------------------------------------
    
    net_book_value = fields.Monetary(
        string="Valeur nette comptable",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Valeur nette comptable de l'immobilisation (book_value)",
    )
    accumulated_depreciation = fields.Monetary(
        string="Amortissements cumulés",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Total des amortissements pratiqués (original_value - book_value)",
    )
    residual_value = fields.Monetary(
        string="Valeur résiduelle",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Valeur résiduelle amortissable (value_residual)",
    )
    inventory_valuation = fields.Monetary(
        string="Valorisation inventaire",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Valorisation pour l'inventaire (égale à la VNC)",
    )
    original_value = fields.Monetary(
        string="Valeur d'origine",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Valeur d'acquisition de l'immobilisation",
    )
    salvage_value = fields.Monetary(
        string="Valeur de récupération",
        compute='_compute_financial_values',
        store=True,
        currency_field='currency_id',
        help="Valeur de récupération prévue en fin d'amortissement",
    )
    
    # Devise
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Devise",
        related='company_id.currency_id',
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('product_id', 'product_id.asset_id')
    def _compute_asset_id(self):
        """
        Calcule l'immobilisation liée depuis le produit.
        
        L'utilisateur peut ensuite modifier manuellement si nécessaire.
        """
        for line in self:
            if line.product_id and line.product_id.asset_id and not line.asset_id:
                line.asset_id = line.product_id.asset_id
            elif not line.product_id:
                line.asset_id = False

    @api.depends('product_id', 'asset_id')
    def _compute_display_name(self):
        """Calcule le nom d'affichage de la ligne."""
        for line in self:
            if line.product_id:
                name = line.product_id.display_name
                if line.asset_id:
                    name = f"{name} [{line.asset_id.name}]"
                line.display_name = name
            else:
                line.display_name = _("Nouvelle ligne")

    @api.depends(
        'asset_id',
        'asset_id.book_value',
        'asset_id.original_value',
        'asset_id.salvage_value',
    )
    def _compute_financial_values(self):
        """
        Calcule les valeurs financières depuis l'immobilisation liée.
        
        Ces champs sont stockés pour permettre le reporting et les recherches,
        mais se mettent à jour automatiquement lorsque l'asset change.
        """
        for line in self:
            asset = line.asset_id
            if asset:
                line.net_book_value = asset.book_value
                line.original_value = asset.original_value
                line.accumulated_depreciation = asset.original_value - asset.book_value
                line.residual_value = asset.value_residual
                line.salvage_value = asset.salvage_value
                line.inventory_valuation = asset.book_value
            else:
                line.net_book_value = 0.0
                line.original_value = 0.0
                line.accumulated_depreciation = 0.0
                line.residual_value = 0.0
                line.salvage_value = 0.0
                line.inventory_valuation = 0.0

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @api.constrains('campaign_id', 'product_id')
    def _check_unique_product_per_campaign(self):
        """Vérifie qu'un produit n'apparaît qu'une fois par campagne."""
        for line in self:
            if line.campaign_id and line.product_id:
                duplicate = self.search([
                    ('campaign_id', '=', line.campaign_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('id', '!=', line.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "Le produit '%s' est déjà présent dans cette "
                        "campagne d'inventaire."
                    ) % line.product_id.display_name)

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Met à jour l'immobilisation et d'autres champs depuis le produit."""
        if self.product_id:
            # Récupérer l'immobilisation liée au produit
            if self.product_id.asset_id:
                self.asset_id = self.product_id.asset_id

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    def action_view_product(self):
        """Ouvre la fiche du produit."""
        self.ensure_one()
        return {
            'name': _("Produit"),
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
        }

    def action_view_asset(self):
        """Ouvre la fiche de l'immobilisation comptable."""
        self.ensure_one()
        if not self.asset_id:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'name': _("Immobilisation"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
        }

    def action_set_present(self):
        """Marque l'équipement comme présent."""
        self.write({'physical_status': 'present'})

    def action_set_missing(self):
        """Marque l'équipement comme manquant."""
        self.write({'physical_status': 'missing'})

    def action_set_degraded(self):
        """Marque l'équipement comme dégradé."""
        self.write({'physical_status': 'degraded'})

    def action_set_to_repair(self):
        """Marque l'équipement comme à réparer."""
        self.write({'physical_status': 'to_repair'})

    def action_print_control_sheet(self):
        """Imprime la fiche de contrôle pour cette ligne."""
        self.ensure_one()
        return self.env.ref(
            'custom_asset_inventory.action_report_fiche_controle'
        ).report_action(self)
