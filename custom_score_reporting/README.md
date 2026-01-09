# SCORE - Reporting

## Overview

Consolidated reporting and dashboard module for the SCORE Logistics Suite. Aggregates KPIs from all SCORE modules into actionable dashboards with pivot reports and quick actions.

## Features

- **Main Dashboard (FR-027)**: Executive overview of fleet status, compliance, costs, maintenance
- **Fleet Overview Pivot (FR-028)**: Multi-dimensional analysis by category, location, status
- **Mission Cost Analysis**: Cost breakdown by project, vehicle, expense type
- **Maintenance Downtime Analysis**: Downtime by typology, technician productivity
- **Fuel Consumption Analysis**: Target vs actual, category comparisons
- **Quick Actions Kanban**: Fast access to common operations
- **Excel Export (FR-029)**: Native Odoo export for all pivot views
- **Cross-Module Consolidation (FR-030)**: Single unified view

## Dependencies

- `custom_score_base`
- `custom_score_vehicle`
- `custom_score_compliance`
- `custom_score_mission_cost`
- `custom_score_maintenance`
- `custom_score_fuel_targets`
- `board` (Odoo native dashboard)

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_reporting
```

## Dashboard Components

### Executive KPIs

| KPI | Description | Source |
|-----|-------------|--------|
| Active Vehicles | Total operational vehicles | `fleet.vehicle` |
| In Maintenance | Vehicles currently under repair | `fleet.maintenance.intervention` |
| Compliance Alerts | Documents expiring within 30 days | `fleet.vehicle.document` |
| Active Missions | Missions in progress | `fleet.mission` |
| Fuel Alerts | Over-consumption warnings/critical | `fleet.fuel.monthly.summary` |

### Pivot Reports Available

1. **Fleet Overview**: Vehicles by category, maintenance state, location
2. **Mission Cost Analysis**: Costs by project, vehicle, expense type, period
3. **Maintenance Analysis**: Downtime by typology, technician hours
4. **Fuel Analysis**: Consumption variance by category, period

### Quick Actions

- View compliance alerts
- View maintenance backlog
- View fuel over-consumption
- Start new mission (if applicable)

## Usage

### Accessing the Dashboard

1. Navigate to **SCORE → Tableau de bord**
2. The main dashboard loads with all KPIs

### Drilling Down

- Click any KPI card to see detailed records
- Use pivot views for multi-dimensional analysis
- Export to Excel using the download button

### Project-Centric View

1. Navigate to **SCORE → Reporting → Par projet**
2. See missions grouped by analytic account/project
3. Aggregate costs and KPIs per project

## Views Included

| View Type | Name | Purpose |
|-----------|------|---------|
| Dashboard | SCORE Tableau de bord | Main executive view |
| Kanban | Quick Actions | Fast navigation |
| Pivot | Fleet Overview | Vehicle analysis |
| Pivot | Mission Cost Analysis | Cost breakdown |
| Pivot | Maintenance Analysis | Downtime reporting |
| Pivot | Fuel Consumption Analysis | Target vs actual |
| Graph | Cost Trends | Cost over time |
| Graph | Consumption Trends | L/100km over time |

## Technical Notes

- Uses Odoo 19 `board` module (AbstractModel pattern)
- All pivot views use `store=True` computed fields for performance
- Dashboard refreshes on page load (no real-time)
- Recommended for Manager/Director role users
- Export uses native Odoo Excel functionality

## Changelog

### 19.0.1.0.0

- Initial release
- Main dashboard with KPI cards
- 4 pivot report templates
- Quick actions kanban
- Project-centric reporting views
- Analytic cost consolidation
