# SCORE - Logistics Suite (Bundle)

## Overview

Meta-module to install the complete SCORE Logistics Suite in a single operation. Installing this module automatically installs all 8 SCORE components with their dependencies.

## What Gets Installed

| Module | Description | FR Coverage |
|--------|-------------|-------------|
| `custom_score_base` | Root menus, cross-cutting utilities | - |
| `custom_score_vehicle` | Vehicle uniqueness, registration, transfers | FR-003/004/008/009/010/011/016 |
| `custom_score_compliance` | Document types, blocking, expiry alerts | FR-007/007a |
| `custom_score_mission_cost` | Mission expenses, cost/km tracking | FR-013/014/015/026 |
| `custom_score_maintenance` | Availability KPIs, downtime tracking | FR-019/020/021/022 |
| `custom_score_fuel_targets` | Consumption targets, variance detection | FR-023/024/025 |
| `custom_score_reporting` | Dashboards, pivot reports, Excel export | FR-027/028/029/030 |
| `custom_score_api` | Optional REST/JSON-RPC endpoints | - |

## Prerequisites

Before installing, ensure these base modules are available and installed:

| Module | Purpose |
|--------|---------|
| `custom_fleet_management` | Base fleet/mission module |
| `custom_fleet_maintenance` | Maintenance interventions |
| `custom_fleet_fuel_management` | Fuel cards, expenses, summaries |
| `stock` | Odoo inventory (for locations/transfers) |
| `analytic` | Odoo analytics (for cost tracking) |

## Installation

### Single Command Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_suite
```

This installs the entire SCORE suite with all dependencies resolved automatically.

### Verify Installation

After installation, verify these menus appear:

- **SCORE** (root menu)
  - Tableau de bord
  - Reporting
  - Configuration

- **Fleet** (extended menus)
  - Registration cases
  - Transfers
  - Document types

## Post-Installation Checklist

1. **Configure Document Types**
   - Navigate to SCORE → Configuration → Document Types
   - Set `is_critical` flag for blocking documents

2. **Set Vehicle Category Targets**
   - Fleet → Configuration → Categories
   - Define L/100km consumption targets per category

3. **Configure Blocking Rules**
   - Fleet → Configuration → Settings
   - Enable/disable mission blocking on expired documents

4. **Assign Security Groups**
   - Settings → Users & Companies → Users
   - Assign SCORE User or SCORE Manager groups

5. **Review Cron Jobs**
   - Settings → Technical → Automation → Scheduled Actions
   - Verify J-30 alerts and weekly reminders are active

## Upgrade

To upgrade all SCORE modules:

```bash
odoo-bin -c odoo.conf -d <database> -u custom_score_suite
```

## Uninstallation

**Important**: Uninstalling `custom_score_suite` will NOT uninstall individual modules.

To fully remove, uninstall each module individually in this order:

1. `custom_score_api` (if installed)
2. `custom_score_reporting`
3. `custom_score_fuel_targets`
4. `custom_score_maintenance`
5. `custom_score_mission_cost`
6. `custom_score_compliance`
7. `custom_score_vehicle`
8. `custom_score_base`

## Technical Notes

- This is a meta-module with no Python code, only dependencies
- Marked as `application=True` for visibility in Apps menu
- Individual modules can also be installed independently
- Version follows Odoo 19 convention: `19.0.1.0.0`

## Support

For issues or questions:

1. Check individual module READMEs for specific documentation
2. Review `specs/002-score-logistics-suite/` for specifications
3. Check `research.md` for design decisions

## Changelog

### 19.0.1.0.0

- Initial release
- Bundles all 8 SCORE modules
- Complete FR coverage (FR-003 through FR-030)
