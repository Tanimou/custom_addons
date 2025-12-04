# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Module: Inventaire des Immobilisations (Custom Asset Inventory)
================================================================

Ce module permet de gérer l'inventaire physique des immobilisations
avec suivi de l'état, localisation et valorisation.

Fonctionnalités principales:
- Campagnes d'inventaire avec périodicité configurable
- Lignes d'inventaire liées aux immobilisations comptables
- Suivi de l'état physique (présent, manquant, dégradé, à réparer)
- Calcul automatique des valeurs comptables
- Assistant de génération des lignes d'inventaire
- Rapports PDF: campagne, écarts, valorisation
"""

from . import models, report, wizard
