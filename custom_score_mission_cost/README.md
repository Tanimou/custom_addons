# SCORE - Mission Cost

## Overview

Mission cost management module for the SCORE Logistics Suite. Tracks mission expenses and provides cost analysis capabilities.

## Features

- **Mission Expenses (FR-014)**: Track toll, fuel, maintenance, and other expenses per mission
- **Cost Consolidation**: Aggregate costs by mission and project
- **Cost/km KPI (FR-015)**: Calculate cost per kilometer (non-blocking if km missing)
- **Approval Traceability (FR-013b/c)**: Track approver user and datetime
- **Analytic Integration (FR-026)**: Propagate expenses to analytic accounts
- **Reporting**: Pivot and graph views for cost analysis

## Dependencies

- `custom_score_base`
- `custom_fleet_management`
- `analytic`

## Models

- `fleet.mission.expense` - Mission expense records
- `fleet.mission` (inherit) - Extended with expense totals and cost/km

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_mission_cost
```

## Configuration

No specific configuration required. Analytic accounts are inherited from project/mission settings.

## Expense Types

- `toll` - Péage
- `fuel` - Carburant
- `maintenance` - Entretien
- `other` - Autre

## Technical Notes

- Cost/km marked as "non calculable" if distance is missing (does not block workflow)
- Approval traceability fields: `approved_by`, `approval_date`
- Expense attachments for justificatifs

## Changelog

### 19.0.1.0.0

- Initial release
- Mission expense model
- Cost/km computation
- Pivot/graph reporting views
