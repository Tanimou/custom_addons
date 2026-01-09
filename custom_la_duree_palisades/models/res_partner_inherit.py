from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re


class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'
    _rec_name = 'name'

    limit_id = fields.Many2one(
        "employee.credit.limit",
        string="Limite de crédit employé"
    )