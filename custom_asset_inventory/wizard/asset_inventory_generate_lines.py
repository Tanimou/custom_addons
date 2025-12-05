# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Wizard: asset.inventory.generate.lines
=======================================

Assistant pour la génération automatique des lignes d'inventaire.

Ce wizard permet de créer des lignes d'inventaire à partir des PRODUITS
qui ont une immobilisation liée, avec des filtres par catégorie, entrepôt,
groupe d'actifs et état de l'immobilisation.
"""

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AssetInventoryGenerateLines(models.TransientModel):
    """Assistant de génération des lignes d'inventaire."""

    _name = 'asset.inventory.generate.lines'
    _description = "Générer les lignes d'inventaire"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    campaign_id = fields.Many2one(
        comodel_name='asset.inventory.campaign',
        string="Campagne",
        required=True,
        ondelete='cascade',
        help="Campagne d'inventaire pour laquelle générer les lignes",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Société",
        related='campaign_id.company_id',
        readonly=True,
    )
    
    # Mode de génération
    generation_mode = fields.Selection(
        selection=[
            ('products_with_assets', 'Produits avec immobilisation'),
            ('all_assets', 'Toutes les immobilisations'),
        ],
        string="Mode de génération",
        default='products_with_assets',
        required=True,
        help="Choisir comment générer les lignes d'inventaire:\n"
             "- Produits avec immobilisation: Génère depuis les produits liés à des immobilisations\n"
             "- Toutes les immobilisations: Génère depuis les immobilisations directement",
    )
    
    # Filtres produits
    product_categ_id = fields.Many2one(
        comodel_name='product.category',
        string="Catégorie produit",
        help="Filtrer par catégorie de produit (optionnel)",
    )
    
    # Filtres de sélection
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Entrepôt",
        domain="[('company_id', '=', company_id)]",
        help="Filtrer par entrepôt (optionnel)",
    )
    location_ids = fields.Many2many(
        comodel_name='stock.location',
        relation='asset_inventory_wizard_location_rel',
        column1='wizard_id',
        column2='location_id',
        string="Emplacements",
        domain="[('company_id', 'in', [company_id, False])]",
        help="Filtrer par emplacements spécifiques (optionnel)",
    )
    asset_group_id = fields.Many2one(
        comodel_name='account.asset.group',
        string="Groupe d'immobilisations",
        domain="[('company_id', 'in', [company_id, False])]",
        help="Filtrer par groupe/catégorie d'immobilisation (optionnel)",
    )
    asset_state = fields.Selection(
        selection=[
            ('all', 'Toutes'),
            ('open', 'En cours'),
            ('paused', 'En pause'),
            ('close', 'Clôturées (amorties)'),
        ],
        string="État des immobilisations",
        default='all',
        required=True,
        help="Filtrer par état comptable des immobilisations",
    )
    
    # Options
    skip_existing = fields.Boolean(
        string="Ignorer les existantes",
        default=True,
        help="Ne pas créer de ligne pour les produits déjà dans la campagne",
    )
    
    # Prévisualisation
    preview_count = fields.Integer(
        string="Nombre de lignes",
        compute='_compute_preview_count',
        help="Nombre de lignes qui seront ajoutées",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends(
        'campaign_id', 'generation_mode', 'product_categ_id',
        'warehouse_id', 'location_ids', 'asset_group_id', 
        'asset_state', 'skip_existing'
    )
    def _compute_preview_count(self):
        """Calcule le nombre de lignes qui seront générées."""
        for wizard in self:
            if wizard.generation_mode == 'products_with_assets':
                products = wizard._get_products_to_generate()
                wizard.preview_count = len(products)
            else:
                assets = wizard._get_assets_to_generate()
                wizard.preview_count = len(assets)

    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------

    def _get_product_domain(self):
        """
        Construit le domaine de recherche des produits.
        
        Returns:
            list: Domaine Odoo pour la recherche des produits
        """
        self.ensure_one()
        
        domain = [
            ('company_id', 'in', [self.company_id.id, False]),
            ('has_asset', '=', True),  # Seulement les produits avec immobilisation
        ]
        
        # Filtre par catégorie produit
        if self.product_categ_id:
            domain.append(('categ_id', 'child_of', self.product_categ_id.id))
        
        # Filtre par groupe d'immobilisation (via l'asset lié)
        if self.asset_group_id:
            domain.append(('asset_id.asset_group_id', '=', self.asset_group_id.id))
        
        # Filtre par état de l'immobilisation
        if self.asset_state and self.asset_state != 'all':
            domain.append(('asset_id.state', '=', self.asset_state))
        else:
            domain.append(('asset_id.state', 'not in', ['model', 'cancelled']))
        
        return domain

    def _get_products_to_generate(self):
        """
        Recherche les produits correspondant aux critères.
        
        Returns:
            recordset: Produits à inclure dans l'inventaire
        """
        self.ensure_one()
        
        domain = self._get_product_domain()
        products = self.env['product.product'].search(domain)
        
        # Exclure les produits déjà dans la campagne si demandé
        if self.skip_existing and self.campaign_id:
            existing_product_ids = self.campaign_id.line_ids.mapped('product_id').ids
            products = products.filtered(lambda p: p.id not in existing_product_ids)
        
        return products

    def _get_asset_domain(self):
        """
        Construit le domaine de recherche des immobilisations.
        
        Returns:
            list: Domaine Odoo pour la recherche des immobilisations
        """
        self.ensure_one()
        
        domain = [
            ('company_id', '=', self.company_id.id),
        ]
        
        # Filtre par état comptable
        if self.asset_state and self.asset_state != 'all':
            domain.append(('state', '=', self.asset_state))
        else:
            domain.append(('state', 'not in', ['model', 'cancelled']))
        
        # Filtre par groupe d'immobilisations
        if self.asset_group_id:
            domain.append(('asset_group_id', '=', self.asset_group_id.id))
        
        return domain

    def _get_assets_to_generate(self):
        """
        Recherche les immobilisations correspondant aux critères.
        
        Returns:
            recordset: Immobilisations à inclure dans l'inventaire
        """
        self.ensure_one()
        
        domain = self._get_asset_domain()
        assets = self.env['account.asset'].search(domain)
        
        # Exclure les immobilisations déjà dans la campagne si demandé
        if self.skip_existing and self.campaign_id:
            existing_asset_ids = self.campaign_id.line_ids.mapped('asset_id').ids
            assets = assets.filtered(lambda a: a.id not in existing_asset_ids)
        
        return assets

    def _prepare_line_values_from_product(self, product):
        """
        Prépare les valeurs pour une ligne d'inventaire depuis un produit.
        
        Args:
            product: recordset product.product
            
        Returns:
            dict: Valeurs pour créer la ligne d'inventaire
        """
        self.ensure_one()
        
        values = {
            'campaign_id': self.campaign_id.id,
            'product_id': product.id,
            'asset_id': product.asset_id.id if product.asset_id else False,
            'responsible_id': self.env.user.id,
        }
        
        # Affecter un emplacement par défaut si spécifié dans le wizard
        if self.location_ids:
            values['location_id'] = self.location_ids[0].id
        
        return values

    def _prepare_line_values_from_asset(self, asset):
        """
        Prépare les valeurs pour une ligne d'inventaire depuis une immobilisation.
        
        Args:
            asset: recordset account.asset
            
        Returns:
            dict: Valeurs pour créer la ligne d'inventaire
        """
        self.ensure_one()
        
        # Chercher un produit lié à cette immobilisation
        product = self.env['product.product'].search([
            ('asset_id', '=', asset.id),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        
        values = {
            'campaign_id': self.campaign_id.id,
            'product_id': product.id if product else False,
            'asset_id': asset.id,
            'responsible_id': self.env.user.id,
        }
        
        if self.location_ids:
            values['location_id'] = self.location_ids[0].id
        
        return values

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    def action_generate(self):
        """
        Génère les lignes d'inventaire selon le mode sélectionné.
        
        Returns:
            dict: Action pour rafraîchir la vue de la campagne
        """
        self.ensure_one()
        
        # Vérifier que la campagne est en brouillon ou en cours
        if self.campaign_id.state not in ('draft', 'in_progress'):
            raise UserError(_(
                "Impossible de générer des lignes pour une campagne "
                "terminée ou annulée."
            ))
        
        Line = self.env['asset.inventory.line']
        lines_vals = []
        
        if self.generation_mode == 'products_with_assets':
            # Générer depuis les produits
            products = self._get_products_to_generate()
            
            if not products:
                raise UserError(_(
                    "Aucun produit avec immobilisation ne correspond aux critères, "
                    "ou tous les produits sont déjà dans la campagne."
                ))
            
            for product in products:
                vals = self._prepare_line_values_from_product(product)
                lines_vals.append(vals)
            
            source_info = _("Produits avec immobilisation")
            
        else:
            # Générer depuis les immobilisations
            assets = self._get_assets_to_generate()
            
            if not assets:
                raise UserError(_(
                    "Aucune immobilisation ne correspond aux critères, "
                    "ou toutes les immobilisations sont déjà dans la campagne."
                ))
            
            for asset in assets:
                vals = self._prepare_line_values_from_asset(asset)
                lines_vals.append(vals)
            
            source_info = _("Immobilisations")
        
        # Création en lot pour de meilleures performances
        created_lines = Line.create(lines_vals)
        
        # Message de confirmation dans le chatter
        # Use Markup to ensure HTML is rendered properly
        body_html = Markup(
            "<p><strong>{title}</strong></p>"
            "<ul>"
            "<li>{lbl_count}: <b>{count}</b></li>"
            "<li>{lbl_source}: {source}</li>"
            "<li>{lbl_categ}: {categ}</li>"
            "<li>{lbl_group}: {group}</li>"
            "<li>{lbl_state}: {state}</li>"
            "</ul>"
        ).format(
            title=_("Génération de lignes d'inventaire"),
            lbl_count=_("Lignes créées"),
            count=len(created_lines),
            lbl_source=_("Source"),
            source=source_info,
            lbl_categ=_("Catégorie produit"),
            categ=self.product_categ_id.name if self.product_categ_id else _("Toutes"),
            lbl_group=_("Groupe d'actifs"),
            group=self.asset_group_id.name if self.asset_group_id else _("Tous"),
            lbl_state=_("État filtré"),
            state=dict(self._fields['asset_state'].selection).get(
                self.asset_state, self.asset_state
            ),
        )
        
        self.campaign_id.message_post(
            body=body_html,
            message_type='notification',
        )
        
        # Retourner à la campagne
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asset.inventory.campaign',
            'res_id': self.campaign_id.id,
            'view_mode': 'form',
        }

    def action_preview(self):
        """
        Affiche la liste des éléments qui seront générés.
        
        Returns:
            dict: Action pour afficher la liste
        """
        self.ensure_one()
        
        if self.generation_mode == 'products_with_assets':
            products = self._get_products_to_generate()
            return {
                'name': _("Produits à inventorier"),
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_mode': 'list,form',
                'domain': [('id', 'in', products.ids)],
                'context': {'create': False},
                'target': 'current',
            }
        else:
            assets = self._get_assets_to_generate()
            return {
                'name': _("Immobilisations à inventorier"),
                'type': 'ir.actions.act_window',
                'res_model': 'account.asset',
                'view_mode': 'list,form',
                'domain': [('id', 'in', assets.ids)],
                'context': {'create': False},
                'target': 'current',
            }
