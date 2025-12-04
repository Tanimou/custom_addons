# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Model: asset.inventory.dashboard
=================================

Dashboard pour l'inventaire des immobilisations.

Ce modèle AbstractModel fournit les données agrégées pour le tableau de bord
de l'inventaire des immobilisations, incluant les KPIs et statistiques.
"""

from odoo import _, api, fields, models


class AssetInventoryDashboard(models.AbstractModel):
    """Dashboard pour l'inventaire des immobilisations."""

    _name = 'asset.inventory.dashboard'
    _description = "Tableau de bord Inventaire Immobilisations"
    _auto = False

    # Dummy id field required for form view compatibility
    id = fields.Id()

    @api.model_create_multi
    def create(self, vals_list):
        """AbstractModel cannot create records."""
        return self

    @api.model
    def get_dashboard_data(self):
        """
        Récupère les données du tableau de bord.
        
        Returns:
            dict: Dictionnaire contenant toutes les métriques du dashboard:
                - total_campaigns: Nombre total de campagnes
                - draft_campaigns: Campagnes en brouillon
                - in_progress_campaigns: Campagnes en cours
                - done_campaigns: Campagnes terminées
                - total_lines: Nombre total de lignes d'inventaire
                - present_count: Immobilisations présentes
                - missing_count: Immobilisations manquantes
                - degraded_count: Immobilisations dégradées
                - to_repair_count: Immobilisations à réparer
                - total_original_value: Valeur d'origine totale
                - total_net_book_value: Valeur nette comptable totale
                - total_accumulated_depreciation: Amortissements cumulés totaux
                - currency_id: ID de la devise de la société
                - recent_campaigns: Liste des campagnes récentes
        """
        company = self.env.company
        currency = company.currency_id
        
        Campaign = self.env['asset.inventory.campaign']
        Line = self.env['asset.inventory.line']
        
        # =====================================================================
        # Campaign Statistics
        # =====================================================================
        campaign_domain = [('company_id', '=', company.id)]
        
        total_campaigns = Campaign.search_count(campaign_domain)
        draft_campaigns = Campaign.search_count(campaign_domain + [('state', '=', 'draft')])
        in_progress_campaigns = Campaign.search_count(campaign_domain + [('state', '=', 'in_progress')])
        done_campaigns = Campaign.search_count(campaign_domain + [('state', '=', 'done')])
        cancel_campaigns = Campaign.search_count(campaign_domain + [('state', '=', 'cancel')])
        
        # =====================================================================
        # Line Statistics - Physical Status
        # =====================================================================
        line_domain = [('company_id', '=', company.id)]
        
        total_lines = Line.search_count(line_domain)
        present_count = Line.search_count(line_domain + [('physical_status', '=', 'present')])
        missing_count = Line.search_count(line_domain + [('physical_status', '=', 'missing')])
        degraded_count = Line.search_count(line_domain + [('physical_status', '=', 'degraded')])
        to_repair_count = Line.search_count(line_domain + [('physical_status', '=', 'to_repair')])
        no_status_count = Line.search_count(line_domain + [('physical_status', '=', False)])
        
        # =====================================================================
        # Financial Statistics (using SQL for performance)
        # =====================================================================
        self.env.cr.execute("""
            SELECT 
                COALESCE(SUM(original_value), 0) as total_original_value,
                COALESCE(SUM(net_book_value), 0) as total_net_book_value,
                COALESCE(SUM(accumulated_depreciation), 0) as total_accumulated_depreciation,
                COALESCE(SUM(inventory_valuation), 0) as total_inventory_valuation
            FROM asset_inventory_line
            WHERE company_id = %s
        """, (company.id,))
        financial_data = self.env.cr.dictfetchone()
        
        # =====================================================================
        # Recent Campaigns (last 5)
        # =====================================================================
        recent_campaigns = Campaign.search(
            campaign_domain,
            limit=5,
            order='create_date desc'
        ).read(['id', 'name', 'code', 'state', 'date_start', 'date_end', 'progress_percent', 'line_count'])
        
        # =====================================================================
        # Active Campaigns (in progress with details)
        # =====================================================================
        active_campaigns = Campaign.search(
            campaign_domain + [('state', '=', 'in_progress')],
            limit=5,
            order='date_start desc'
        ).read(['id', 'name', 'code', 'progress_percent', 'line_count', 'line_present_count', 'line_missing_count'])
        
        # =====================================================================
        # Statistics by Periodicity
        # =====================================================================
        periodicity_stats = Campaign.read_group(
            campaign_domain,
            ['periodicity'],
            ['periodicity'],
        )
        
        # =====================================================================
        # Statistics by State
        # =====================================================================
        state_stats = Campaign.read_group(
            campaign_domain,
            ['state'],
            ['state'],
        )
        
        # Calculate inventory completion rate
        inventory_rate = 0.0
        if total_lines > 0:
            inventoried_count = present_count + missing_count + degraded_count + to_repair_count
            inventory_rate = (inventoried_count / total_lines) * 100
        
        # Calculate asset condition rate (present vs total inventoried)
        asset_condition_rate = 0.0
        inventoried_total = present_count + missing_count + degraded_count + to_repair_count
        if inventoried_total > 0:
            asset_condition_rate = (present_count / inventoried_total) * 100
        
        return {
            # Campaign counts
            'total_campaigns': total_campaigns,
            'draft_campaigns': draft_campaigns,
            'in_progress_campaigns': in_progress_campaigns,
            'done_campaigns': done_campaigns,
            'cancel_campaigns': cancel_campaigns,
            
            # Line counts
            'total_lines': total_lines,
            'present_count': present_count,
            'missing_count': missing_count,
            'degraded_count': degraded_count,
            'to_repair_count': to_repair_count,
            'no_status_count': no_status_count,
            
            # Financial values
            'total_original_value': financial_data['total_original_value'],
            'total_net_book_value': financial_data['total_net_book_value'],
            'total_accumulated_depreciation': financial_data['total_accumulated_depreciation'],
            'total_inventory_valuation': financial_data['total_inventory_valuation'],
            
            # Currency
            'currency_id': currency.id,
            'currency_symbol': currency.symbol,
            'currency_position': currency.position,
            
            # Rates
            'inventory_rate': round(inventory_rate, 1),
            'asset_condition_rate': round(asset_condition_rate, 1),
            
            # Lists
            'recent_campaigns': recent_campaigns,
            'active_campaigns': active_campaigns,
            'periodicity_stats': periodicity_stats,
            'state_stats': state_stats,
            
            # Company info
            'company_id': company.id,
            'company_name': company.name,
        }
    
    @api.model
    def get_campaign_trend_data(self, period='month', limit=12):
        """
        Récupère les données de tendance des campagnes.
        
        Args:
            period: 'month', 'quarter', ou 'year'
            limit: Nombre de périodes à récupérer
            
        Returns:
            list: Liste de dictionnaires avec les données par période
        """
        company = self.env.company
        Campaign = self.env['asset.inventory.campaign']
        
        if period == 'month':
            date_trunc = 'month'
        elif period == 'quarter':
            date_trunc = 'quarter'
        else:
            date_trunc = 'year'
        
        self.env.cr.execute("""
            SELECT 
                DATE_TRUNC(%s, date_start) as period,
                COUNT(*) as campaign_count,
                SUM(line_count) as total_lines
            FROM asset_inventory_campaign
            WHERE company_id = %s
              AND date_start IS NOT NULL
            GROUP BY DATE_TRUNC(%s, date_start)
            ORDER BY period DESC
            LIMIT %s
        """, (date_trunc, company.id, date_trunc, limit))
        
        return self.env.cr.dictfetchall()
    
    @api.model
    def get_status_distribution_data(self):
        """
        Récupère la distribution des statuts physiques.
        
        Returns:
            list: Liste de dictionnaires avec les données par statut
        """
        company = self.env.company
        Line = self.env['asset.inventory.line']
        
        return Line.read_group(
            [('company_id', '=', company.id)],
            ['physical_status'],
            ['physical_status'],
        )
    
    @api.model
    def get_value_by_location_data(self):
        """
        Récupère les valeurs par emplacement.
        
        Returns:
            list: Liste de dictionnaires avec les valeurs par location
        """
        company = self.env.company
        
        self.env.cr.execute("""
            SELECT 
                l.location_id,
                sl.complete_name as location_name,
                COUNT(l.id) as line_count,
                SUM(l.net_book_value) as total_net_book_value,
                SUM(l.original_value) as total_original_value
            FROM asset_inventory_line l
            LEFT JOIN stock_location sl ON l.location_id = sl.id
            WHERE l.company_id = %s
              AND l.location_id IS NOT NULL
            GROUP BY l.location_id, sl.complete_name
            ORDER BY total_net_book_value DESC
            LIMIT 10
        """, (company.id,))
        
        return self.env.cr.dictfetchall()
