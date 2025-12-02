# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FleetFuelBalanceService(models.AbstractModel):
    _name = "fleet.fuel.balance.service"
    _description = "Service de gestion des soldes de cartes"

    def _ensure_card(self, card):
        if not card:
            raise ValidationError(_("Carte carburant introuvable."))
        return card.sudo()

    def reserve_amount(self, card, amount):
        card = self._ensure_card(card)
        if amount <= 0:
            return
        card.pending_amount += amount
        _logger.debug("Reserve %.2f on card %s", amount, card.name)

    def release_amount(self, card, amount):
        card = self._ensure_card(card)
        if amount <= 0:
            return
        card.pending_amount = max(card.pending_amount - amount, 0.0)
        _logger.debug("Release %.2f on card %s", amount, card.name)

    def apply_delta(self, card, amount):
        card = self._ensure_card(card)
        card.balance_amount += amount
        _logger.debug("Apply delta %.2f on card %s", amount, card.name)

    def spend_amount(self, card, amount):
        card = self._ensure_card(card)
        if amount <= 0:
            return
        if card.available_amount < amount:
            raise ValidationError(_("Solde insuffisant pour la carte %s") % card.name)
        card.balance_amount -= amount
        _logger.debug("Spend %.2f on card %s", amount, card.name)