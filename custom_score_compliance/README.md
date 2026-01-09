# SCORE - Compliance

## Overview

Document compliance module for the SCORE Logistics Suite. Manages critical document types, mission blocking rules, and automated alerts.

## Features

- **Document Types (FR-007a)**: Configurable document types with `is_critical` flag
- **Mission Blocking**: Block mission submit/start when critical documents are expired
- **J-30 Alerts (FR-007)**: Automated alerts 30 days before document expiry
- **Weekly Reminders**: Recurring reminders for expiring/expired documents
- **Configurable Enforcement**: Settings to control blocking behavior

## Dependencies

- `custom_score_base`
- `custom_fleet_management`
- `mail` (for activities/reminders)

## Models

- `fleet.vehicle.document.type` - Document type master with criticality flag
- `fleet.vehicle.document` (inherit) - Extended with `document_type_id` Many2one
- `fleet.vehicle` (inherit) - Helper methods for expired critical docs
- `fleet.mission` (inherit) - Blocking logic on state transitions
- `res.config.settings` (inherit) - Compliance configuration toggles

## Configuration

Go to Fleet > Configuration > Settings and configure:

- **Block on Submit**: Block mission submission if critical docs expired (default: True)
- **Block on Start**: Block mission start if critical docs expired (default: True)
- **Block on Create**: Optionally block at creation (default: False)
- **Warn on Vehicle Change**: Show warning when selecting vehicle with issues

## Cron Jobs

- `ir_cron_vehicle_doc_d30_alert`: Daily check for J-30 expiring documents
- `ir_cron_vehicle_doc_weekly_reminder`: Weekly reminder for expired/expiring docs

## Migration Notes

This module introduces a Selection → Many2one migration for `document_type`:

1. Creates `fleet.vehicle.document.type` records with stable `code` values
2. Adds `document_type_id` field to `fleet.vehicle.document`
3. Backfills existing documents on install via `post_init_hook`
4. Business logic uses `document_type_id` when set, falls back to legacy Selection

## Technical Notes

- Config settings use `custom_score_compliance_` prefix
- Config parameter keys use `custom_score_compliance.` namespace
- Cron jobs use Odoo 19 compliant fields only (no `numbercall`, `doall`, etc.)

## Changelog

### 19.0.1.0.0

- Initial release
- Document type model with criticality
- Mission blocking logic
- J-30 and weekly alert crons
- Migration/compatibility layer
