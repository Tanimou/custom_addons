# SCORE - API

## Overview

Optional REST/JSON-RPC API module for external integrations with the SCORE Logistics Suite.

## Features

- **Vehicle Endpoints**: Read vehicle data, status, compliance
- **Mission Endpoints**: Mission lifecycle operations
- **Document Endpoints**: Document status and expiry queries
- **Standard Authentication**: Uses Odoo session/token authentication

## Dependencies

- `custom_score_base`
- `custom_score_vehicle`
- `custom_score_compliance`
- `custom_score_mission_cost`

## Installation

```bash
odoo-bin -c odoo.conf -d <database> -i custom_score_api
```

**Note**: This module is optional. The SCORE suite functions fully without it.

## API Endpoints

Endpoints will be implemented as needed. Placeholder structure:

- `GET /score/api/v1/vehicles` - List vehicles
- `GET /score/api/v1/vehicles/<id>` - Vehicle details
- `GET /score/api/v1/missions` - List missions
- `POST /score/api/v1/missions/<id>/start` - Start mission
- `GET /score/api/v1/compliance/alerts` - Compliance alerts

## Security

- All endpoints require authentication
- Uses Odoo's standard session or API key authentication
- Respects existing access rights and record rules

## Technical Notes

- Controllers in `controllers/` directory
- JSON responses with standard error handling
- CORS configuration if needed for external clients

## Changelog

### 19.0.1.0.0

- Initial release
- Placeholder controller structure
