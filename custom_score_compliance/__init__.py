# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

from . import models

# Export post_init_hook for __manifest__.py
from .models.fleet_vehicle_document_type import _post_init_hook_backfill_document_types
