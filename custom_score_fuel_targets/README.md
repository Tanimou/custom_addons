# SCORE - Fuel Targets

## Overview

Fuel consumption targets module for the SCORE Logistics Suite. Enables comparison of actual L/100km consumption against family-based targets with automatic over-consumption alerts.

## Features

- **Consumption Targets (FR-024)**: Define L/100km target per vehicle family/category
- **Variance Detection**: Calculate delta between actual and target consumption (L/100km and %)
- **Over-consumption Alerts (FR-025)**: Automatic 4-level alerts (OK, Warning, Critical, Non-calculable)
- **Vehicle Fuel History (FR-023)**: Smart button with detailed expense history per vehicle
- **Reporting**: Pivot views with target vs actual analysis

## Dependencies

- `custom_score_base`
- `custom_fleet_fuel_management`
- `custom_fleet_management`

## Models Extended

| Model | Extension |
|-------|-----------|
| `fleet.vehicle.model.category` | `target_consumption_l100km` (Float), `target_consumption_notes` (Text), vehicle/alert counts |
| `fleet.fuel.monthly.summary` | `target_variance_l100km`, `target_variance_pct`, `consumption_alert_level` (Selection) |
| `fleet.fuel.expense` | `vehicle_category_id` (related field for filtering) |
| `fleet.vehicle` | `fuel_expense_count`, `total_fuel_amount`, `total_fuel_liters`, `active_consumption_alert` |

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_fuel_targets
```

## Configuration

### 1. Define Consumption Targets

1. Navigate to **Fleet → Configuration → Categories**
2. Open a vehicle category (e.g., "Utilitaires")
3. Set the **Cible L/100km** field (e.g., 9.5 for utility vehicles)
4. Add notes explaining the target source/conditions

### 2. Default Categories (Seed Data)

The module includes example targets:

| Category | Target L/100km |
|----------|---------------|
| Voitures de service | 7.0 |
| Utilitaires | 9.5 |
| Frigorifiques | 12.0 |
| Poids Lourds | 32.0 |
| Engins de chantier | 45.0 |

## Alert Logic

### Alert Levels

| Level | Condition | Color |
|-------|-----------|-------|
| **OK** | Actual ≤ Target | 🟢 Green |
| **Warning** | Actual > Target by >10% | 🟡 Yellow |
| **Critical** | Actual > Target by >20% | 🔴 Red |
| **Non-calculable** | Missing distance, liters, or target | ⚪ Grey |

### Variance Calculation

```
Variance (L/100km) = Actual Consumption - Target Consumption
Variance (%) = (Variance / Target) × 100

Example:
  Actual: 11.0 L/100km
  Target: 9.5 L/100km
  Variance: +1.5 L/100km (+15.8%) → Warning
```

## Usage

### View Fuel History per Vehicle

1. Open a vehicle form view
2. Click the **"Pleins"** smart button to see all fuel expenses
3. Click **"Synthèses carburant"** button for monthly summaries

### Monitor Consumption Alerts

1. Navigate to **Fuel → Monthly Summaries**
2. Use filters: "Alerte conso: Warning" or "Alerte conso: Critical"
3. Group by **Famille** to see which categories have issues

### Category Alert Overview

1. Navigate to **Fleet → Configuration → Categories**
2. The **Alertes consommation** column shows active alerts per category
3. Click to see all summaries with warnings/critical alerts

## Views Added

- Category form/tree: Target field + alert counts
- Fuel summary tree: Target, variance, alert columns
- Fuel summary form: Target comparison section
- Fuel summary search: Alert level filters + category grouping
- Vehicle form/tree: Fuel smart buttons + alert badge

## Technical Notes

- Family model uses native `fleet.vehicle.model.category` (simple, upgrade-safe)
- Alert thresholds are constants: 10% (Warning), 20% (Critical)
- All computed fields have `store=True` for efficient pivot/filtering
- Non-calculable state does NOT block any workflow (informational only)
- Uses existing fuel sequences from `custom_fleet_fuel_management`

## Changelog

### 19.0.1.0.0

- Initial release
- Family target field on `fleet.vehicle.model.category`
- Variance computation (L/100km and %)
- 4-level alert system on `fleet.fuel.monthly.summary`
- Vehicle fuel history smart buttons
- Seed data with 5 example categories
