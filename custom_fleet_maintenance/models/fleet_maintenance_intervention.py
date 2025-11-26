from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class FleetMaintenanceIntervention(models.Model):
    _name = "fleet.maintenance.intervention"
    _description = "Intervention de maintenance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_start desc, id desc"

    name = fields.Char(string="Reference", copy=False, default="/")
    intervention_type = fields.Selection(
        selection=[("preventive", "Preventive"), ("curative", "Curative")],
        string="Type",
        required=True,
        default="curative",
        tracking=True,
    )
    failure_type = fields.Selection(
        selection=[
            ("moteur", "Moteur"),
            ("transmission", "Transmission"),
            ("electrique", "Électrique"),
            ("pneu", "Pneu"),
            ("freins", "Freins"),
            ("carrosserie", "Carrosserie"),
            ("climatisation", "Climatisation"),
            ("direction", "Direction"),
            ("suspension", "Suspension"),
            ("autre", "Autre"),
        ],
        string="Type de panne",
        tracking=True,
        help="Type de panne ou dysfonctionnement signalé",
    )
    origin = fields.Char(string="Origine")
    vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicule",
        required=True,
        tracking=True,
    )
    driver_id = fields.Many2one(
        "res.partner",
        string="Conducteur",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Societe",
        required=True,
        default=lambda self: self.env.company,
    )
    plan_line_id = fields.Many2one("fleet.maintenance.plan.line", string="Plan preventif")
    request_date = fields.Datetime(string="Date de demande", default=fields.Datetime.now)
    scheduled_start = fields.Datetime(string="Debut planifie")
    scheduled_end = fields.Datetime(string="Fin planifiee")
    actual_start = fields.Datetime(string="Debut reel")
    actual_end = fields.Datetime(string="Fin reelle")
    close_date = fields.Datetime(string="Date de cloture")
    odometer = fields.Float(string="Kilometrage releve")
    location_id = fields.Many2one("stock.location", string="Lieu d'immobilisation")
    responsible_id = fields.Many2one("res.users", string="Responsable", tracking=True)
    technician_id = fields.Many2one("res.users", string="Technicien")
    vendor_id = fields.Many2one("res.partner", string="Prestataire", domain="[('supplier_rank', '>', 0)]")
    priority = fields.Selection(
        selection=[("0", "Normale"), ("1", "Haute"), ("2", "Urgente"), ("3", "Critique")],
        default="0",
    )
    severity = fields.Selection(
        selection=[("low", "Faible"), ("medium", "Moyenne"), ("high", "Elevee")],
        default="medium",
    )
    description = fields.Html(string="Description", sanitize_style=True)
    failure_note = fields.Text(string="Diagnostic")
    intervention_report = fields.Html(
        string="Rapport d'intervention",
        sanitize_style=True,
        help="Rapport détaillé de l'intervention réalisée (pièces remplacées, travaux effectués, observations)",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("submitted", "Soumise"),
            ("in_progress", "En cours"),
            ("done", "Terminee"),
            ("cancelled", "Annulee"),
        ],
        default="draft",
        tracking=True,
    )
    document_ids = fields.Many2many("ir.attachment", string="Pieces jointes")
    part_line_ids = fields.One2many("fleet.maintenance.part.line", "intervention_id", string="Couts")
    purchase_order_ids = fields.Many2many("purchase.order", string="Commandes d'achat")
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    part_amount = fields.Monetary(string="Pieces", compute="_compute_cost_totals", store=True)
    labor_amount = fields.Monetary(string="Main-d'oeuvre", compute="_compute_cost_totals", store=True)
    subcontract_amount = fields.Monetary(string="Sous-traitance", compute="_compute_cost_totals", store=True)
    other_amount = fields.Monetary(string="Autre", compute="_compute_cost_totals", store=True)
    purchase_amount = fields.Monetary(string="Couts achats", compute="_compute_cost_totals", store=True)
    total_amount = fields.Monetary(string="Cout estime", compute="_compute_cost_totals", store=True)
    actual_total_amount = fields.Monetary(string="Cout reel", compute="_compute_cost_totals", store=True)
    calendar_event_id = fields.Many2one("calendar.event", string="Evenement calendrier")
    purchase_order_count = fields.Integer(compute="_compute_purchase_order_count", store=True)
    picking_id = fields.Many2one("stock.picking", string="Transfert stock")
    next_planned_date = fields.Date(string="Date suivante")
    next_planned_odometer = fields.Float(string="KM suivant")
    is_overdue = fields.Boolean(compute="_compute_is_overdue", store=True)

    def _get_sequence_code(self):
        return (
            "custom_fleet_maintenance.seq_preventive_intervention"
            if self.intervention_type == "preventive"
            else "custom_fleet_maintenance.seq_curative_intervention"
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            intervention_type = vals.get("intervention_type", "curative")
            seq_code = (
                "custom_fleet_maintenance.seq_preventive_intervention"
                if intervention_type == "preventive"
                else "custom_fleet_maintenance.seq_curative_intervention"
            )
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(seq_code)
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
        records = super().create(vals_list)
        records._post_create_updates()
        return records

    def _post_create_updates(self):
        for record in self:
            if record.vehicle_id and not record.driver_id:
                record.driver_id = record.vehicle_id.driver_id
            if record.intervention_type == "curative" and record.vehicle_id:
                record.vehicle_id.maintenance_state = "breakdown"

    @api.onchange('intervention_type')
    def _onchange_filter_available_vehicles(self):
        """Filter vehicle dropdown to show only available vehicles if the field exists."""
        # Check if is_available field exists (defined in custom_fleet_management)
        if 'is_available' in self.env['fleet.vehicle']._fields:
            return {'domain': {'vehicle_id': [('is_available', '=', True)]}}
        return {'domain': {'vehicle_id': []}}

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ["state", "intervention_type"]):
            self._sync_vehicle_state()
        return res

    def _sync_vehicle_state(self):
        for record in self:
            if not record.vehicle_id:
                continue
            open_interventions = record.vehicle_id.maintenance_history_ids.filtered(
                lambda r: r.state not in ("done", "cancelled")
            )
            if open_interventions:
                record.vehicle_id.maintenance_state = "maintenance"
            else:
                record.vehicle_id.maintenance_state = "operational"

    @api.constrains("vehicle_id", "driver_id")
    def _check_driver_vehicle_access(self):
        if not self.env.user.has_group("custom_fleet_maintenance.group_fleet_maintenance_driver"):
            return
        partner = self.env.user.partner_id
        for record in self:
            if record.driver_id and record.driver_id != partner:
                raise ValidationError(_("Vous ne pouvez declarer que des interventions pour votre propre vehicule."))
            if record.vehicle_id and record.vehicle_id.driver_id and record.vehicle_id.driver_id != partner:
                raise ValidationError(_("Ce vehicule n'est pas assigne a votre profil."))

    @api.depends("part_line_ids.subtotal", "part_line_ids.cost_type", "purchase_order_ids.amount_total")
    def _compute_cost_totals(self):
        for record in self:
            part_amount = sum(record.part_line_ids.filtered(lambda l: l.cost_type == "part").mapped("subtotal"))
            labor_amount = sum(record.part_line_ids.filtered(lambda l: l.cost_type == "labor").mapped("subtotal"))
            subcontract_amount = sum(record.part_line_ids.filtered(lambda l: l.cost_type == "subcontract").mapped("subtotal"))
            other_amount = sum(
                record.part_line_ids.filtered(lambda l: l.cost_type not in ("part", "labor", "subcontract")).mapped("subtotal")
            )
            purchase_amount = sum(record.purchase_order_ids.mapped("amount_total"))
            record.part_amount = part_amount
            record.labor_amount = labor_amount
            record.subcontract_amount = subcontract_amount
            record.other_amount = other_amount
            record.purchase_amount = purchase_amount
            record.total_amount = part_amount + labor_amount + subcontract_amount + other_amount
            record.actual_total_amount = record.total_amount + purchase_amount

    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = len(record.purchase_order_ids)

    @api.depends("scheduled_end", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_overdue = bool(record.scheduled_end and record.scheduled_end < now and record.state not in ("done", "cancelled"))

    def action_submit(self):
        self._change_state("submitted")

    def action_start(self):
        for record in self:
            if record.state != "submitted":
                raise UserError(_("L'intervention doit etre soumise avant de demarrer."))
            # Set vehicle in maintenance state when intervention starts
            if record.vehicle_id:
                record.vehicle_id.write({'maintenance_state': 'maintenance'})
        self._change_state("in_progress", {"actual_start": fields.Datetime.now()})

    def action_done(self):
        update_vals = {
            "actual_end": fields.Datetime.now(),
            "close_date": fields.Datetime.now(),
        }
        self._change_state("done", update_vals)
        for record in self:
            if record.plan_line_id:
                record.plan_line_id.last_execution_id = record
                record.plan_line_id._compute_next_threshold()
            record.vehicle_id._update_preventive_dates()
            # Update vehicle mileage if odometer was recorded
            if record.odometer and record.vehicle_id:
                if record.odometer > record.vehicle_id.odometer:
                    record.vehicle_id.odometer = record.odometer
            # Log completion in vehicle chatter
            if record.vehicle_id:
                failure_label = dict(record._fields['failure_type'].selection).get(record.failure_type, '') if record.failure_type else ''
                msg = _("Intervention %s terminée. %s Coût total: %s %s") % (
                    record.name,
                    f"Type de panne: {failure_label}. " if failure_label else "",
                    record.actual_total_amount,
                    record.currency_id.symbol or '',
                )
                record.vehicle_id.message_post(body=msg, message_type='notification')
            # Check if vehicle can be set available after maintenance completion
            if record.vehicle_id:
                # Only check for in_progress interventions - submitted doesn't block vehicle
                other_in_progress = self.env['fleet.maintenance.intervention'].search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('id', '!=', record.id),
                    ('state', '=', 'in_progress')
                ])
                if not other_in_progress:
                    # No other in-progress interventions - set vehicle to operational
                    record.vehicle_id.write({'maintenance_state': 'operational'})

    def action_cancel(self):
        self._change_state("cancelled")
        # Update vehicle availability after cancellation
        for record in self:
            if record.vehicle_id:
                # Only check for in_progress interventions - submitted doesn't block vehicle
                other_in_progress = self.env['fleet.maintenance.intervention'].search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('id', '!=', record.id),
                    ('state', '=', 'in_progress')
                ])
                if not other_in_progress:
                    # No other in-progress interventions - set vehicle to operational
                    record.vehicle_id.write({'maintenance_state': 'operational'})

    def _change_state(self, state, extra_vals=None):
        values = {"state": state}
        if extra_vals:
            values.update(extra_vals)
        self.write(values)

    def action_schedule_calendar(self):
        config = self.env["ir.config_parameter"].sudo()
        sync_enabled = config.get_param("custom_fleet_maintenance.calendar_sync_enabled", "True")
        if str(sync_enabled).lower() in ("false", "0"):
            return True
        CalendarEvent = self.env["calendar.event"]
        for record in self:
            if record.calendar_event_id:
                event = record.calendar_event_id
            else:
                event = CalendarEvent.create(
                    {
                        "name": record.name,
                        "partner_ids": [(6, 0, record._get_calendar_partners())],
                        "start": record.scheduled_start,
                        "stop": record.scheduled_end or record.scheduled_start,
                        "allday": False,
                        "description": record.description,
                    }
                )
                record.calendar_event_id = event
        return True

    def _get_calendar_partners(self):
        partners = self.env["res.partner"]
        for record in self:
            if record.responsible_id:
                partners |= record.responsible_id.partner_id
            if record.technician_id:
                partners |= record.technician_id.partner_id
            if record.vendor_id:
                partners |= record.vendor_id
        return partners.ids

    def _get_vendor(self):
        vendor = self.vendor_id or self.part_line_ids.filtered(lambda l: l.vendor_id)[:1].vendor_id
        if not vendor:
            raise UserError(_("Definissez un prestataire ou un fournisseur sur l'intervention ou les lignes."))
        return vendor

    def action_create_purchase_order(self):
        self.ensure_one()
        line_commands = self._prepare_purchase_lines()
        vendor = self._get_vendor()
        order_vals = {
            "partner_id": vendor.id,
            "origin": self.name,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "order_line": line_commands,
        }
        order = self.env["purchase.order"].sudo().create(order_vals)
        self.purchase_order_ids = [(4, order.id)]
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["res_id"] = order.id
        action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        return action

    def _prepare_purchase_lines(self):
        lines = []
        cost_lines = self.part_line_ids.filtered(lambda l: l.cost_type in ("part", "subcontract"))
        if not cost_lines:
            raise UserError(_("Ajoutez au moins une ligne de piece ou sous-traitance avec un article pour generer un achat."))
        for cost_line in cost_lines:
            if not cost_line.product_id:
                raise UserError(_("Les lignes de pieces doivent avoir un article pour generer un achat."))
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": cost_line.product_id.id,
                        "name": cost_line.description or cost_line.product_id.display_name,
                        "product_qty": cost_line.quantity,
                        "product_uom_id": cost_line.uom_id.id or cost_line.product_id.uom_id.id,
                        "price_unit": cost_line.unit_price,
                        "date_planned": self.scheduled_start or fields.Datetime.now(),
                        "analytic_distribution": cost_line.analytic_account_id
                        and {str(cost_line.analytic_account_id.id): 100}
                        or False,
                    },
                )
            )
        return lines

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        if len(self.purchase_order_ids) == 1:
            action["res_id"] = self.purchase_order_ids.id
            action["views"] = [(self.env.ref("purchase.purchase_order_form").id, "form")]
        else:
            action["domain"] = [("id", "in", self.purchase_order_ids.ids)]
        return action

    def _get_internal_picking_type(self):
        self.ensure_one()
        picking_type = (
            self.env["stock.picking.type"]
            .sudo()
            .search([("code", "=", "internal"), ("warehouse_id.company_id", "in", [self.company_id.id, False])], limit=1)
        )
        if not picking_type:
            raise UserError(_("Aucun type de transfert interne n'a ete trouve pour la societe."))
        if not picking_type.default_location_src_id:
            warehouse = picking_type.warehouse_id
            if warehouse and warehouse.lot_stock_id:
                picking_type = picking_type.with_context(default_location_src_id=warehouse.lot_stock_id.id)
        return picking_type

    def _prepare_stock_moves(self, picking_type, dest_location):
        moves = []
        location_src = picking_type.default_location_src_id or (picking_type.warehouse_id and picking_type.warehouse_id.lot_stock_id)
        if not location_src:
            raise UserError(_("Aucun emplacement source defini pour le transfert interne."))
        for cost_line in self.part_line_ids.filtered(
            lambda l: l.cost_type == "part" and l.product_id and l.product_id.type in ("product", "consu")
        ):
            moves.append(
                (
                    0,
                    0,
                    {
                        "name": cost_line.description or cost_line.product_id.display_name,
                        "product_id": cost_line.product_id.id,
                        "product_uom": cost_line.uom_id.id or cost_line.product_id.uom_id.id,
                        "product_uom_qty": cost_line.quantity,
                        "company_id": self.company_id.id,
                        "location_id": location_src.id,
                        "location_dest_id": dest_location.id,
                    },
                )
            )
        return moves

    def action_create_stock_transfer(self):
        self.ensure_one()
        dest_location = self.location_id or self.vehicle_id.maintenance_location_id
        if not dest_location:
            raise UserError(_("Definissez un emplacement de maintenance sur l'intervention ou le vehicule."))
        picking_type = self._get_internal_picking_type()
        moves = self._prepare_stock_moves(picking_type, dest_location)
        if not moves:
            raise UserError(_("Aucune piece stockable a transferer. Verifiez les lignes de cout avec un article."))
        picking_vals = {
            "picking_type_id": picking_type.id,
            "origin": self.name,
            "company_id": self.company_id.id,
            "location_id": (picking_type.default_location_src_id or picking_type.warehouse_id.lot_stock_id).id,
            "location_dest_id": dest_location.id,
            "move_ids": moves,
        }
        picking = self.env["stock.picking"].sudo().create(picking_vals)
        self.picking_id = picking.id
        action = self.env.ref("stock.action_picking_tree_all").sudo().read()[0]
        action["res_id"] = picking.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        return action

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return False
        action = self.env.ref("stock.action_picking_tree_all").sudo().read()[0]
        action["res_id"] = self.picking_id.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        return action

    @api.model
    def cron_send_alerts(self):
        config = self.env["ir.config_parameter"].sudo()
        offset = int(config.get_param("custom_fleet_maintenance.alert_offset_days", 30))
        today = fields.Date.context_today(self)
        limit_date = today + timedelta(days=offset)
        now_time = fields.Datetime.now().time()
        domain = [
            ("state", "in", ["draft", "submitted"]),
            ("scheduled_start", "!=", False),
            ("scheduled_start", "<=", datetime.combine(limit_date, now_time)),
        ]
        interventions = self.search(domain)
        template = self.env.ref("custom_fleet_maintenance.mail_template_maintenance_alert", raise_if_not_found=False)
        todo_activity = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        responsible_param = int(config.get_param("custom_fleet_maintenance.default_responsible_id", 0) or 0)
        fallback_user = responsible_param or self.env.user.id
        for intervention in interventions:
            if template:
                template.send_mail(intervention.id, force_send=False)
            user_id = intervention.responsible_id.id or fallback_user
            existing_activity = self.env["mail.activity"]
            if todo_activity:
                existing_activity = intervention.activity_ids.filtered(
                    lambda act: act.activity_type_id == todo_activity and act.user_id.id == user_id and act.state == "planned"
                )
            if not existing_activity:
                intervention.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Maintenance a planifier"),
                    note=_("L'intervention %s arrive a echeance.") % intervention.name,
                    user_id=user_id,
                )

    @api.model
    def cron_send_digest(self):
        config = self.env["ir.config_parameter"].sudo()
        weekly_enabled = config.get_param("custom_fleet_maintenance.weekly_digest_enabled", "True")
        if str(weekly_enabled).lower() in ("false", "0"):
            return
        interventions = self.search([("state", "in", ["submitted", "in_progress"]), ("company_id", "=", self.env.company.id)])
        if not interventions:
            return
        template = self.env.ref("custom_fleet_maintenance.mail_template_weekly_digest", raise_if_not_found=False)
        for responsible in interventions.mapped("responsible_id"):
            responsible_interventions = interventions.filtered(lambda r: r.responsible_id == responsible)
            if template and responsible_interventions:
                template.with_context(interventions=responsible_interventions).send_mail(responsible_interventions[0].id, force_send=False)

    def get_vehicle_stats(self, limit=5):
        if not self:
            return []
        groups = self.env["fleet.maintenance.intervention"].read_group(
            domain=[("id", "in", self.ids), ("vehicle_id", "!=", False)],
            fields=["vehicle_id", "actual_total_amount:sum"],
            groupby=["vehicle_id"],
            orderby="__count desc",
        )
        stats = []
        for group in groups:
            vehicle = self.env["fleet.vehicle"].browse(group["vehicle_id"][0])
            stats.append(
                {
                    "vehicle": vehicle,
                    "count": group.get("__count", 0),
                    "amount": group.get("actual_total_amount_sum", 0.0),
                }
            )
        return stats[:limit]
