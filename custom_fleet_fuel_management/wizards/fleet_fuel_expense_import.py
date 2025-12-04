# -*- coding: utf-8 -*-
import base64
import csv
import logging
from io import BytesIO, StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

try:
    import openpyxl
except ImportError:
    openpyxl = None

_logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"card_uid", "expense_date", "amount", "liter_qty"}


class FleetFuelExpenseImportWizard(models.TransientModel):
    _name = "fleet.fuel.expense.import.wizard"
    _description = "Assistant d'import de dépenses carburant"

    data_file = fields.Binary(string="Fichier (XLSX ou CSV)", required=True)
    filename = fields.Char(string="Nom du fichier")
    company_id = fields.Many2one("res.company", string="Société", default=lambda self: self.env.company, required=True)
    auto_validate = fields.Boolean(string="Valider automatiquement", default=True)
    batch_id = fields.Many2one("fleet.fuel.expense.batch", string="Lot existant")
    note = fields.Text(string="Commentaire")

    def action_import(self):
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Veuillez sélectionner un fichier à importer."))
        _logger.info("Starting fuel expense import from file %s", self.filename or "unknown")
        batch = self.batch_id or self._create_batch()
        batch.set_processing()
        lines = self._parse_file()
        _logger.info("Parsed %d lines from file", len(lines))
        expense_model = self.env["fleet.fuel.expense"].sudo()
        errors = False
        created_count = 0
        skipped_count = 0
        for idx, row in enumerate(lines, start=2):
            expense = False
            try:
                vals = self._prepare_expense_vals(row, batch, line_number=idx)
                if not vals:
                    batch.log_line(state="skipped", message=_("Ligne %s ignorée : données insuffisantes") % idx)
                    skipped_count += 1
                    continue
                duplicate = False
                if vals.get("import_hash"):
                    duplicate = expense_model.search([("import_hash", "=", vals["import_hash"]), ("company_id", "=", batch.company_id.id)], limit=1)
                if duplicate:
                    batch.log_line(
                        state="skipped",
                        import_hash=vals.get("import_hash"),
                        expense_id=duplicate.id,
                        message=_("Ligne %s ignorée : dépense déjà importée") % idx,
                    )
                    skipped_count += 1
                    continue
                expense = expense_model.create(vals)
                if self.auto_validate:
                    expense.action_validate()
                batch.log_line(
                    state="done",
                    expense_id=expense.id,
                    import_hash=expense.import_hash,
                    message=_("Ligne %s importée avec succès") % idx,
                )
                created_count += 1
            except Exception as exc:  # pylint: disable=broad-except
                errors = True
                _logger.warning("Import error on line %d: %s", idx, exc)
                batch.log_line(
                    state="error",
                    expense_id=expense.id if expense else False,
                    message=_("Ligne %(line)s : %(msg)s") % {"line": idx, "msg": str(exc)},
                )
        batch.set_finished(has_error=errors)
        _logger.info("Import finished: %d created, %d skipped, errors=%s", created_count, skipped_count, errors)
        
        # Build notification message in French
        error_count = len(lines) - created_count - skipped_count
        if errors:
            message = _("Import terminé avec erreurs : %(created)d créée(s), %(skipped)d ignorée(s), %(errors)d erreur(s)") % {
                "created": created_count,
                "skipped": skipped_count,
                "errors": error_count,
            }
            fade_out = "slow"
        else:
            if skipped_count:
                message = _("Import réussi : %(created)d dépense(s) créée(s), %(skipped)d ignorée(s) (doublons)") % {
                    "created": created_count,
                    "skipped": skipped_count,
                }
            else:
                message = _("Import réussi : %d dépense(s) créée(s)") % created_count
            fade_out = "medium"
        
        # Return redirect to expense list with notification effect
        return {
            "type": "ir.actions.act_window",
            "res_model": "fleet.fuel.expense",
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
            "domain": [("batch_id", "=", batch.id)] if created_count else [],
            "name": _("Dépenses importées"),
            "effect": {
                "fadeout": fade_out,
                "message": message,
                "type": "rainbow_man",
            },
        }

    def _create_batch(self):
        name = self.filename or _("Import dépenses %s") % fields.Datetime.now()
        return self.env["fleet.fuel.expense.batch"].create(
            {
                "name": name,
                "company_id": self.company_id.id,
                "import_filename": self.filename,
                "log_message": self.note,
            }
        )

    def _parse_file(self):
        raw = base64.b64decode(self.data_file)
        extension = (self.filename or "csv").split(".")[-1].lower()
        if extension in {"xls", "xlsx", "xlsm"}:
            if not openpyxl:
                raise UserError(_("Le module openpyxl n'est pas installé. Veuillez utiliser un fichier CSV."))
            workbook = openpyxl.load_workbook(BytesIO(raw), read_only=True, data_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                raise ValidationError(_("Le fichier Excel est vide."))
            headers = [str(cell or "").strip().lower() for cell in rows[0]]
            missing = REQUIRED_COLUMNS - set(headers)
            if missing:
                raise ValidationError(_("Colonnes obligatoires manquantes : %s") % ", ".join(sorted(missing)))
            data = []
            for row in rows[1:]:
                row_dict = {}
                for idx, header in enumerate(headers):
                    value = row[idx] if idx < len(row) else None
                    if value is not None:
                        row_dict[header] = str(value) if not isinstance(value, str) else value
                    else:
                        row_dict[header] = ""
                data.append(row_dict)
            return data
        else:
            text = raw.decode("utf-8-sig")
            reader = csv.DictReader(StringIO(text))
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValidationError(_("Colonnes obligatoires manquantes : %s") % ", ".join(sorted(missing)))
            return list(reader)

    def _prepare_expense_vals(self, row, batch, line_number=0):
        card_uid = (row.get("card_uid") or "").strip()
        if not card_uid:
            raise ValidationError(_("Carte manquante"))
        card = self.env["fleet.fuel.card"].search(
            [("card_uid", "=", card_uid), ("company_id", "=", batch.company_id.id)], limit=1
        )
        if not card:
            raise ValidationError(_("Carte %s introuvable") % card_uid)
        expense_date = row.get("expense_date")
        try:
            expense_date = fields.Date.to_date(expense_date)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValidationError(_("Date invalide pour %s") % expense_date) from exc
        amount = self._to_float(row.get("amount"))
        liter_qty = self._to_float(row.get("liter_qty"))
        if not amount:
            raise ValidationError(_("Montant invalide pour la carte %s") % card_uid)
        expense_model = self.env["fleet.fuel.expense"].with_company(batch.company_id)
        import_hash = expense_model._make_import_hash(card.id, expense_date, amount, liter_qty)
        station_name = (row.get("station") or row.get("station_name") or "").strip()
        station_partner = False
        if station_name:
            station_partner = self.env["res.partner"].search(
                [("name", "=", station_name), ("company_id", "in", [batch.company_id.id, False]), ("supplier_rank", ">", 0)],
                limit=1,
            )
        vals = {
            "card_id": card.id,
            "vehicle_id": card.vehicle_id.id,
            "driver_id": card.driver_id.id,
            "expense_date": expense_date,
            "amount": amount,
            "liter_qty": liter_qty,
            "company_id": batch.company_id.id,
            "currency_id": card.currency_id.id,
            "station_partner_id": station_partner.id if station_partner else False,
            "notes": row.get("notes") or row.get("comment"),
            "batch_id": batch.id,
            "import_hash": import_hash,
        }
        odometer = row.get("odometer")
        if odometer:
            vals["odometer"] = self._to_float(odometer)
        receipt_payload = self._extract_receipt_payload(row, line_number, card_uid, expense_date)
        vals.update(receipt_payload)
        return vals

    @staticmethod
    def _to_float(value):
        if isinstance(value, (int, float)):
            return float(value)
        value = (value or "").strip()
        if not value:
            return 0.0
        normalized = value.replace(" ", "").replace(",", ".")
        return float(normalized)

    def _extract_receipt_payload(self, row, line_number, card_uid, expense_date):
        """Extract receipt attachment from row data. Returns empty dict if no receipt provided."""
        attachment_b64 = row.get("receipt_b64") or row.get("receipt_data")
        if not attachment_b64:
            # Receipt is optional - return empty dict, user can add later
            return {}
        if attachment_b64.startswith("data:"):
            attachment_b64 = attachment_b64.split(",", 1)[-1]
        filename = row.get("receipt_filename")
        return {
            "receipt_attachment": attachment_b64,
            "receipt_filename": filename or f"justificatif_{card_uid}_{expense_date}.bin",
        }