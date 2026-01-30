# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_print_proforma_company(self):
        """
        Print the correct proforma invoice based on the active company.
        - MYRED TRAVELS → MYRED proforma
        - Others (ICARE) → ICARE proforma
        """
        self.ensure_one()
        if 'myred' in (self.env.company.name or '').lower():
            report_action = self.env.ref('custom_shipment_tracking.action_report_sale_order_proforma_myred')
        else:
            report_action = self.env.ref('custom_shipment_tracking.action_report_sale_order_proforma_invoice')
        return report_action.report_action(self)
