from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de create pour vérifier avant création du paiement
        """
        payments = super().create(vals_list)
        
        for payment in payments:

            if payment.payment_method_id.is_limit_credit:
                payment._check_manager_pos()
                
        return payments
    

    def _check_manager_pos(self):
        """
        Verifie si le responsable du POS a effectuer le paiement
        """
        manager = self.env.user.has_group('custom_la_duree_palisades.group_sale_manager_pos')

        if not manager:
            raise UserError(_("Le responsable du POS doit effectuer le paiement"))

class PosPaymentMethodInherit(models.Model):
    _inherit = 'pos.payment.method'

    is_limit_credit = fields.Boolean('En cours / Compte client')




