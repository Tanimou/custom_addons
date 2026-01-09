# SCORE - Base

## Overview

Base module for the SCORE Logistics Suite. This module provides the foundational structure including root menus and cross-cutting elements for all SCORE modules.

## Features

- Root menu structure for SCORE suite
- Cross-cutting UI elements
- Base dependencies management

## Dependencies

- `custom_fleet_management` (existing fleet management module)

## Installation

1. Ensure `custom_fleet_management` is installed
2. Install this module via Odoo Apps or command line:

   ```bash
   odoo-bin -c odoo.conf -d <database> -i custom_score_base
   ```

## Configuration

No specific configuration required. This module serves as the foundation for other SCORE modules.

## Technical Notes

- This module must be installed before any other `custom_score_*` module
- All SCORE domain modules depend on this base module

## Changelog

### 19.0.1.0.0

- Initial release
- Root menu structure
