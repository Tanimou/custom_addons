from odoo import models, fields, api,_, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
import re
import logging
_logger = logging.getLogger(__name__)

class ProductTemplateInherit(models.Model):
    _inherit = "product.template"


    is_chick = fields.Boolean(string="Est un poussin", store=True)
    is_egg = fields.Boolean(string="Est un oeuf", store=True)