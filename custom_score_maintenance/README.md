# SCORE - Maintenance

## Overview

Maintenance delta module for the SCORE Logistics Suite. Extends maintenance features with downtime tracking and productivity KPIs.

## Features

- **Downtime Calculation (FR-019)**: Computed from actual_start to actual_end (fallback to scheduled)
- **Technician Productivity (FR-022)**: Time tracking per technician with productivity indicators
- **Maintenance Typology (FR-021)**: Curative/preventive classification
- **Parts/Stock Hooks (FR-020)**: Integration with stock consumption and procurement

## Dependencies

- `custom_score_base`
- `custom_fleet_maintenance`

## Models

- `fleet.maintenance.intervention` (inherit) - Extended with downtime fields
- `fleet.maintenance.technician.time` - Time entries per technician
- `fleet.vehicle` (inherit) - Vehicle state integration with interventions

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_maintenance
```

## Configuration

No specific configuration required. Uses existing maintenance setup.

## Downtime Calculation

- Primary: `actual_start` → `actual_end`
- Fallback: `scheduled_start` → `scheduled_end` if actual dates missing
- Stored computed field for reporting performance

## Technical Notes

- Downtime fields are `store=True` for efficient filtering/reporting
- Productivity KPIs computed on-demand for flexibility
- Audit existing coverage before adding new features (per research.md)

## Changelog

### 19.0.1.0.0

- Initial release
- Downtime KPI fields
- Technician time tracking model
- Reporting views
