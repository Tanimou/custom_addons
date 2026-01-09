from odoo import models, fields, api,_, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
import re
import logging
_logger = logging.getLogger(__name__)

class EggCollectionProject(models.Model):
    _name = "egg.collection.project"
    _rec_name = 'product_id'
    _description = "Collection d'oeufs"


    product_id = fields.Many2one(
        'product.product', 
        string="Produit", 
        required=True, 
        domain=[('product_tmpl_id.is_egg', '=', True)])
    quantity = fields.Float("Nombre plaquettes d'oeufs", required=True, default=0.0)
    t_quantity = fields.Float("Total d'oeufs", compute='compute_t_quantity')
    broken_eggs = fields.Integer("Nombre d'oeufs cassé", required=True, default=0.0)
    project_id = fields.Many2one('project.project', string="Projet/Cycle d'élevage", required=True)
    Chicken_coop = fields.Many2one(related='project_id.Chicken_coop', string="Poulailler")
    lot_strip = fields.Many2one(related='project_id.lot_strip', string="Lot/Bande Associé")
    purchase_id = fields.Many2one(related='project_id.purchase_id', string="Bons de commande fournisseur")
    origin = fields.Char(string='Référence', default='Collecte d\'oeufs')
    date = fields.Date('Date', default=fields.Date.context_today)
    picking_id = fields.Many2one('stock.picking', string="Dossier de livraison", copy=False, readonly=True)
    state = fields.Selection([('draft', 'En attente'), ('done', 'Valider')], default='draft', readonly=True)
    note = fields.Text(string='Notes')

    @api.onchange('quantity')
    def compute_t_quantity(self):
        for record in self:
            record.t_quantity = record.quantity * 30


    @api.model
    def create(self, vals):
        res = super(EggCollectionProject, self).create(vals)
        for record in res:
            record.action_create_reception()
        return res

    # def get_product_egg_carton(self):
    #     Product = self.env['product.product']
    #     produit = Product.search([('name', '=', "Carton d'oeuf")], limit=1)
        
    #     if not produit:
    #         try:
    #             produit = self.env.ref('custom_kedousha.product_egg_carton_chickens').id
    #         except ValueError:
    #             produit = False       
    #     self.product_id = produit.id if produit else False

    def action_create_reception(self):
        """Créer la réception à partir du wizard"""
        self.ensure_one()
        
        # Préparer les données des produits
        products_data = []
        for line in self:
            products_data.append({
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'lot_name': line.lot_strip.name if line.lot_strip else None,
            })
        
        # Créer la réception
        partner = self.env.user.partner_id
        picking = self.env['stock.picking'].create_reception_without_purchase(
            partner_id=partner.id,
            products_data=products_data,
            origin=self.origin,
            scheduled_date=self.date,
            note=self.note,
            egg_id=self.id
        )
        self.picking_id = picking.id
        # Retourner l'action pour ouvrir le picking créé
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }
