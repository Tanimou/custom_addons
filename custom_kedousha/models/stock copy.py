from odoo import models, fields, api,_, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
import re
import logging
_logger = logging.getLogger(__name__)

class StockLocationInherit(models.Model):
    _inherit = "stock.location"


    user_ids = fields.Many2many('res.users', string="Responsables")


class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    project_id = fields.Many2one('project.project', string="Projet", copy=False)
    is_project = fields.Boolean(string="Generer un nouveau projet", store=True)
    name_project = fields.Char(string="Nom du projet", store=True, readonly=False)
    number_chicks_received = fields.Integer('Nombre de poussin reçu', default=0, compute='_compute_number_chicks_received', store=True)
    type_operation = fields.Selection(
        [
            ('broiler', 'Poussin de chair'), 
            ('laying', 'Poussin pondeur'), 
            ('egg', 'Oeufs'), 
            ('feed', 'Aliment pour volailles'),
        ], 
        string="Type de reception", store=True,)
    egg_id = fields.Many2one('egg.collection.project', string="Collecte d'oeufs", copy=False, readonly=True)

    @api.depends('move_ids_without_package')
    def _compute_number_chicks_received(self):
        for picking in self:
            total_chicks = sum(line.quantity for line in picking.move_ids_without_package if line.product_id.product_tmpl_id.is_chick)
            picking.number_chicks_received = total_chicks


    def create_new_project(self):
        project_obj = self.env['project.project']
        for picking in self:
            if not picking.name_project:
                raise UserError(_('Veuillez saisir un nom pour le projet.'))
            if not picking.project_id:
                project = project_obj.create({
                    'name': picking.name_project,
                    'picking_id': picking.id,
                    'Chicken_coop': picking.location_dest_id.id,
                    'date_chicks_received': picking.date_deadline,
                    'number_chicks_received': picking.number_chicks_received,
                    'purchase_id': picking.purchase_id.id or picking.origin and self.env['purchase.order'].search([('name', '=', picking.origin)], limit=1).id or False,
                })
                picking.project_id = project.id
        return True 
    
    def open_project_form(self):
        """Ouvre la vue forme du projet sélectionné"""
        if not self.project_id:
            raise UserError(_('Aucun projet n\'est associé à cet enregistrement.'))
        
        if not self.project_id.exists():
            raise UserError(_('Le projet associé n\'existe plus en base de données.'))
        
        return {
            'name': _('Projet: {}').format(self.project_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': self.project_id.id,  # ID spécifique du projet
            'view_mode': 'form',           # Force la vue forme
            'views': [(False, 'form')],    # Uniquement la vue forme
            'target': 'current',           # Remplace la vue actuelle
            'context': {
                'create': False,           # Pas de création
                'edit': True,             # Permet l'édition
                'form_view_initial_mode': 'edit'
            }
        }
    
    def button_validate(self):
        res = super(StockPickingInherit, self).button_validate()
        eggs = self.env['egg.collection.project'].search([('picking_id', 'in', self.ids)])
        if eggs:
            for egg in eggs:
                egg.state = 'done'
        return res
    
    # def unlink(self):
    #     for picking in self:
    #         if picking.project_id:
    #             raise UserError(_('Vous ne pouvez pas supprimer une réception liée à un projet.'))
    #         if picking.egg_id:
    #             raise UserError(_('Vous ne pouvez pas supprimer une réception liée à une collecte d\'oeufs.'))
    #     return super(StockPickingInherit, self).unlink()

    def create_reception_without_purchase(self, partner_id, products_data, 
                                         location_dest_id=None, origin=None, 
                                         scheduled_date=None, note=None, egg_id=None):
        """
        Créer une réception (picking entrant) sans bon de commande
        
        Args:
            partner_id (int): ID du fournisseur/partenaire
            products_data (list): Liste de dictionnaires avec les infos produits
                Format: [
                    {
                        'product_id': int,
                        'quantity': float,
                        'lot_name': str (optionnel),
                        'package_id': int (optionnel)
                    },
                    ...
                ]
            location_dest_id (int, optional): ID de l'emplacement de destination
            origin (str, optional): Référence d'origine
            scheduled_date (datetime, optional): Date planifiée
            note (str, optional): Notes additionnelles
            
        Returns:
            stock.picking: Le picking créé
        """
        
        # Validation des paramètres
        if not partner_id:
            raise UserError("Le partenaire (fournisseur) est obligatoire.")
        
        if not products_data or not isinstance(products_data, list):
            raise UserError("Les données produits doivent être une liste non vide.")
        
        # Récupération du partenaire
        partner = self.env['res.partner'].browse(partner_id)
        if not partner.exists():
            raise UserError(f"Le partenaire avec l'ID {partner_id} n'existe pas.")
        
        # Récupération du type d'opération (réception)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id.company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not picking_type:
            raise UserError("Aucun type d'opération 'Réception' trouvé pour cette société.")
        
        # Emplacement de destination par défaut (stock)
        if not location_dest_id:
            location_dest_id = picking_type.default_location_dest_id.id
        
        # Emplacement source (fournisseur)
        location_src_id = self.env.ref('stock.stock_location_suppliers').id
        
        # Date planifiée par défaut
        if not scheduled_date:
            scheduled_date = fields.Datetime.now()
        
        # Création du picking (réception)
        picking_vals = {
            'partner_id': partner_id,
            'picking_type_id': picking_type.id,
            'location_id': location_src_id,
            'location_dest_id': location_dest_id,
            'origin': origin or f'Réception Manuelle - {partner.name}',
            'scheduled_date': scheduled_date,
            'note': note,
            'egg_id': egg_id,
            'move_type': 'direct',  # Livraison dès que possible
        }
        
        picking = self.create(picking_vals)
        
        # Création des lignes de mouvement (stock.move)
        for product_data in products_data:
            self._create_stock_move(picking, product_data, location_src_id, location_dest_id)
        
        # Confirmer le picking
        if picking.state == 'draft':
            picking.action_confirm()
        
        return picking
    

    def _create_stock_move(self, picking, product_data, location_src_id, location_dest_id):
        """
        Crée un mouvement de stock pour un produit, sans forcer la création de lots.
        Si un numéro de lot est fourni, il est créé/lié automatiquement.
        Sinon, les lots pourront être saisis manuellement dans l'interface.
        """
        product_id = product_data.get('product_id')
        quantity = product_data.get('quantity', 0)

        if not product_id:
            raise UserError("L'ID du produit est obligatoire pour chaque ligne.")
        if quantity <= 0:
            raise UserError(f"La quantité doit être positive pour le produit ID {product_id}.")

        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            raise UserError(f"Le produit avec l'ID {product_id} n'existe pas.")

        move_vals = {
            'name': product.display_name,
            'product_id': product_id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': location_src_id,
            'location_dest_id': location_dest_id,
            'origin': picking.origin,
            'picking_type_id': picking.picking_type_id.id,
        }
        move = self.env['stock.move'].create(move_vals)

        # Ne créer la ligne que si le lot est spécifié (sinon saisie manuelle)
        lot_name = product_data.get('lot_name')
        package_id = product_data.get('package_id')

        if lot_name:
            move._action_confirm()

            lot = self.env['stock.lot'].search([
                ('name', '=', lot_name),
                ('product_id', '=', product_id),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            if not lot:
                lot = self.env['stock.lot'].create({
                    'name': lot_name,
                    'product_id': product_id,
                    'company_id': self.env.company.id,
                })

            move_line_vals = {
                'move_id': move.id,
                'product_id': product_id,
                'product_uom_id': product.uom_id.id,
                'location_id': location_src_id,
                'location_dest_id': location_dest_id,
                'qty_done': quantity,
                'picking_id': picking.id,
                'lot_id': lot.id,
            }

            if package_id:
                move_line_vals['package_id'] = package_id
                move_line_vals['result_package_id'] = package_id

            self.env['stock.move.line'].create(move_line_vals)

        return move
    
    # def _create_stock_move(self, picking, product_data, location_src_id, location_dest_id):
    #     """
    #     Créer un mouvement de stock pour un produit
        
    #     Args:
    #         picking: Le picking associé
    #         product_data: Dictionnaire avec les données du produit
    #         location_src_id: ID emplacement source
    #         location_dest_id: ID emplacement destination
    #     """
    #     product_id = product_data.get('product_id')
    #     quantity = product_data.get('quantity', 0)
        
    #     if not product_id:
    #         raise UserError("L'ID du produit est obligatoire pour chaque ligne.")
        
    #     if quantity <= 0:
    #         raise UserError(f"La quantité doit être positive pour le produit ID {product_id}.")
        
    #     # Récupération du produit
    #     product = self.env['product.product'].browse(product_id)
    #     if not product.exists():
    #         raise UserError(f"Le produit avec l'ID {product_id} n'existe pas.")
        
    #     # Valeurs du mouvement
    #     move_vals = {
    #         'name': product.display_name,
    #         'product_id': product_id,
    #         'product_uom_qty': quantity,
    #         'product_uom': product.uom_id.id,
    #         'picking_id': picking.id,
    #         'location_id': location_src_id,
    #         'location_dest_id': location_dest_id,
    #         'origin': picking.origin,
    #         'picking_type_id': picking.picking_type_id.id,
    #     }
        
    #     move = self.env['stock.move'].create(move_vals)
        
    #     # Si un numéro de lot est spécifié
    #     lot_name = product_data.get('lot_name')
    #     package_id = product_data.get('package_id')
        
    #     if lot_name or package_id:
    #         # Créer les move lines avec lot/package
    #         move._action_confirm()
    #         move_line_vals = {
    #             'move_id': move.id,
    #             'product_id': product_id,
    #             'product_uom_id': product.uom_id.id,
    #             'location_id': location_src_id,
    #             'location_dest_id': location_dest_id,
    #             'qty_done': quantity,
    #             'picking_id': picking.id,
    #         }
            
    #         if lot_name and product.tracking != 'none':
    #             # Créer ou récupérer le lot
    #             lot = self.env['stock.lot'].search([
    #                 ('name', '=', lot_name),
    #                 ('product_id', '=', product_id),
    #                 ('company_id', '=', self.env.company.id)
    #             ], limit=1)
                
    #             if not lot:
    #                 lot = self.env['stock.lot'].create({
    #                     'name': lot_name,
    #                     'product_id': product_id,
    #                     'company_id': self.env.company.id,
    #                 })
                
    #             move_line_vals['lot_id'] = lot.id
            
    #         if package_id:
    #             move_line_vals['package_id'] = package_id
    #             move_line_vals['result_package_id'] = package_id
            
    #         self.env['stock.move.line'].create(move_line_vals)
        
    #     return move
