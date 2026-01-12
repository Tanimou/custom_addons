# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

"""
Extension of fleet.fuel.monthly.summary with target consumption comparison (FR-024/FR-025).

Adds:
- Target consumption from vehicle category
- Variance calculation (L/100km and %)
- Consumption alert level (ok/warning/critical/non_calculable)
"""

from odoo import _, api, fields, models

# Threshold for warning: variance % above target
CONSUMPTION_WARNING_THRESHOLD = 10.0  # 10% over target = warning
CONSUMPTION_CRITICAL_MULTIPLIER = 2.0  # 2x warning threshold = critical (20%)


class FleetFuelMonthlySummaryTarget(models.Model):
    """Extend fuel monthly summary with target comparison."""
    
    _inherit = 'fleet.fuel.monthly.summary'

    # -------------------------------------------------------------------------
    # CATEGORY / TARGET FIELDS
    # -------------------------------------------------------------------------
    category_id = fields.Many2one(
        related='vehicle_id.category_id',
        string="Famille véhicule",
        store=True,
        help="Catégorie/famille du véhicule (pour cible consommation)",
    )
    
    target_consumption_l100km = fields.Float(
        related='category_id.target_consumption_l100km',
        string="Cible L/100km",
        store=True,
        help="Consommation cible de la famille de véhicules",
    )

    # -------------------------------------------------------------------------
    # VARIANCE FIELDS
    # -------------------------------------------------------------------------
    target_variance_l100km = fields.Float(
        string="Écart L/100km",
        compute="_compute_target_variance",
        store=True,
        digits=(6, 2),
        help="Écart entre consommation réelle et cible (positif = surconsommation)",
    )
    
    target_variance_pct = fields.Float(
        string="Écart %",
        compute="_compute_target_variance",
        store=True,
        digits=(5, 1),
        help="Écart en pourcentage par rapport à la cible",
    )
    
    is_over_target = fields.Boolean(
        string="Dépasse cible",
        compute="_compute_target_variance",
        store=True,
        help="Vrai si la consommation réelle dépasse la cible",
    )

    # -------------------------------------------------------------------------
    # ALERT LEVEL
    # -------------------------------------------------------------------------
    consumption_alert_level = fields.Selection(
        selection=[
            ('non_calculable', 'Non calculable'),
            ('ok', 'OK'),
            ('warning', 'Attention'),
            ('critical', 'Critique'),
        ],
        string="Alerte conso",
        compute="_compute_consumption_alert_level",
        store=True,
        help="Niveau d'alerte basé sur l'écart à la cible:\n"
             "- OK: consommation ≤ cible\n"
             "- Attention: dépassement > 10%\n"
             "- Critique: dépassement > 20%\n"
             "- Non calculable: données manquantes",
    )
    
    consumption_alert_message = fields.Char(
        string="Message alerte",
        compute="_compute_consumption_alert_level",
        store=False,
        help="Message détaillant la situation de consommation",
    )

    # -------------------------------------------------------------------------
    # COMPUTED METHODS
    # -------------------------------------------------------------------------
    @api.depends(
        'avg_consumption_per_100km',
        'target_consumption_l100km',
        'distance_traveled',
        'total_liter',
    )
    def _compute_target_variance(self):
        """
        Calculate variance between actual and target consumption.
        
        Variance = actual - target
        Positive variance = over-consumption (bad)
        Negative variance = under target (good)
        """
        for summary in self:
            actual = summary.avg_consumption_per_100km or 0.0
            target = summary.target_consumption_l100km or 0.0
            
            # Check if calculation is possible
            if not target or not actual:
                summary.target_variance_l100km = 0.0
                summary.target_variance_pct = 0.0
                summary.is_over_target = False
                continue
            
            # Calculate variance
            variance = actual - target
            variance_pct = (variance / target) * 100.0 if target else 0.0
            
            summary.target_variance_l100km = round(variance, 2)
            summary.target_variance_pct = round(variance_pct, 1)
            summary.is_over_target = variance > 0

    @api.depends(
        'avg_consumption_per_100km',
        'target_consumption_l100km',
        'target_variance_pct',
        'distance_traveled',
        'total_liter',
    )
    def _compute_consumption_alert_level(self):
        """
        Determine alert level based on consumption variance.
        
        Levels:
        - non_calculable: Missing data (no distance, no liters, no target)
        - ok: At or below target
        - warning: Over target by > CONSUMPTION_WARNING_THRESHOLD (10%)
        - critical: Over target by > CONSUMPTION_WARNING_THRESHOLD * CONSUMPTION_CRITICAL_MULTIPLIER (20%)
        """
        for summary in self:
            actual = summary.avg_consumption_per_100km
            target = summary.target_consumption_l100km
            distance = summary.distance_traveled
            liters = summary.total_liter
            variance_pct = summary.target_variance_pct
            
            # Check for missing data
            if not distance or distance <= 0:
                summary.consumption_alert_level = 'non_calculable'
                summary.consumption_alert_message = _("Distance non renseignée")
                continue
                
            if not liters or liters <= 0:
                summary.consumption_alert_level = 'non_calculable'
                summary.consumption_alert_message = _("Litres non renseignés")
                continue
                
            if not target or target <= 0:
                summary.consumption_alert_level = 'non_calculable'
                summary.consumption_alert_message = _("Cible consommation non définie pour cette famille")
                continue
            
            if not actual or actual <= 0:
                summary.consumption_alert_level = 'non_calculable'
                summary.consumption_alert_message = _("Consommation moyenne non calculée")
                continue
            
            # Determine alert level based on variance
            critical_threshold = CONSUMPTION_WARNING_THRESHOLD * CONSUMPTION_CRITICAL_MULTIPLIER
            
            if variance_pct > critical_threshold:
                summary.consumption_alert_level = 'critical'
                summary.consumption_alert_message = _(
                    "Surconsommation critique: +%(pct).1f%% (>%(threshold).0f%%)",
                    pct=variance_pct,
                    threshold=critical_threshold,
                )
            elif variance_pct > CONSUMPTION_WARNING_THRESHOLD:
                summary.consumption_alert_level = 'warning'
                summary.consumption_alert_message = _(
                    "Surconsommation: +%(pct).1f%% (>%(threshold).0f%%)",
                    pct=variance_pct,
                    threshold=CONSUMPTION_WARNING_THRESHOLD,
                )
            else:
                summary.consumption_alert_level = 'ok'
                if variance_pct <= 0:
                    summary.consumption_alert_message = _(
                        "Consommation optimale: %(actual).2f L/100km (cible: %(target).2f)",
                        actual=actual,
                        target=target,
                    )
                else:
                    summary.consumption_alert_message = _(
                        "Consommation acceptable: +%(pct).1f%% (seuil alerte: %(threshold).0f%%)",
                        pct=variance_pct,
                        threshold=CONSUMPTION_WARNING_THRESHOLD,
                    )

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def get_consumption_status_color(self):
        """Return color code for consumption status display."""
        self.ensure_one()
        colors = {
            'non_calculable': 'secondary',
            'ok': 'success',
            'warning': 'warning', 
            'critical': 'danger',
        }
        return colors.get(self.consumption_alert_level, 'secondary')
