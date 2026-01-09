# SCORE - Vehicle

## Overview

Delta module for vehicle/equipment management in the SCORE Logistics Suite. Extends `fleet.vehicle` with SCORE-specific features.

## Features

- **Conditional Uniqueness (FR-004)**: VIN unique if set, license plate unique if set
- **Internal Identifier (FR-003)**: Auto-assigned immutable vehicle code
- **Registration Cases (FR-008/FR-008a)**: Workflow with rejection reason required
- **Operational Status History (FR-011)**: Track status changes with audit trail
- **Vehicle Transfers (FR-016)**: Site-to-site transfers with validation workflow
- **Reception Expenses (FR-009)**: Track vehicle acquisition costs
- **Driver/Team KPIs (FR-010)**: Days worked, kilometers, missions indicators

## Dependencies

- `custom_score_base`
- `custom_fleet_management`
- `stock` (for location management)

## Models

- `fleet.vehicle` (inherit) - Extended with uniqueness constraints, internal identifier, location
- `fleet.vehicle.registration.case` - Registration workflow with states
- `fleet.vehicle.transfer` - Transfer workflow between locations
- `fleet.vehicle.reception.expense` - Vehicle acquisition expenses
- `fleet.vehicle.operational.status.history` - Status change tracking (if dedicated model approach)

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_vehicle
```

## Configuration

No specific configuration required beyond standard fleet setup.

## Technical Notes

- Uses Python `@api.constrains` for conditional uniqueness (not SQL constraint)
- Transfers integrate with `stock.location` for site management
- Status history uses `mail.tracking` or dedicated model per research decision

## Changelog

### 19.0.1.0.0

- Initial release
- Conditional uniqueness constraints
- Registration case workflow
- Transfer workflow
- Operational status tracking
