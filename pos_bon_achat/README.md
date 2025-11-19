# POS Bon d'achat

## Description

This module extends Odoo's loyalty program functionality to add a new program type: **Bon d'achat** (Purchase Voucher).

Bon d'achat vouchers are single-use, POS-only vouchers that can be generated and distributed to customers. Unlike regular discount coupons, bon d'achat vouchers:

- Can only be used **once** in Point of Sale
- Are **fully consumed** after use, even if the order total is less than the voucher amount
- Are **not available** in eCommerce or website sales
- Have a **monetary value** that can be applied to any order

## Features

### Backend Features

1. **New Program Type**: Adds "Bon d'achat" to the loyalty program types
2. **Generation Wizard**: Generate multiple bon d'achat vouchers with specific amounts
3. **State Management**: Track voucher state (Active, Used, Expired)
4. **Single-Use Enforcement**: Automatically marks vouchers as used after validation
5. **Usage History**: Complete audit trail of when and where vouchers were used
6. **French Language Support**: All labels and messages in French

### POS Features

1. **Dedicated Button**: "Bon d'achat" button in POS control panel
2. **Code Entry**: Simple code entry popup with validation
3. **Smart Application**:
   - If order total ≤ voucher amount: Order total becomes 0
   - If order total > voucher amount: Remaining amount is displayed
4. **Reuse Prevention**: Already-used vouchers are rejected with clear error messages
5. **Receipt Display**: Voucher application clearly shown on receipts

## Installation

1. Copy the `pos_bon_achat` module to your Odoo addons directory
2. Update the apps list: Settings → Apps → Update Apps List
3. Install the module: Search for "POS Bon d'achat" and click Install

## Configuration

### Creating a Bon d'achat Program

1. Go to: **Point of Sale → Products → Remise & Fidélité**
2. Click **Create** and select **Bon d'achat** template
3. Configure the program:
   - **Name**: Give your program a name (e.g., "Bons d'achat 2024")
   - **Validity Period**: Set start/end dates if needed
   - The program is automatically configured with:
     - Single use (max_usage = 1)
     - POS-only access
     - Monetary reward type

### Generating Bon d'achat Vouchers

1. Open your Bon d'achat program
2. Click **Generate Coupons** button
3. Configure generation:
   - **For**: Choose "Anonymous Customers" or "Selected Customers"
   - **Montant du bon**: Enter the monetary amount (e.g., 50.00 for 50€)
   - **Quantity**: Number of vouchers to generate
   - **Valid Until**: Optional expiration date
4. Click **Generate**
5. The system creates unique codes for each voucher

### Configuring the BON ACHAT payment method

1. Navigate to **Point of Sale → Configuration → Payment Methods**
2. Create a new payment method (or edit an existing one dedicated to vouchers)
3. Set the journal that should receive voucher redemptions
4. Enable the checkbox **Bon d'achat payment method**
5. Assign this payment method to every POS configuration that accepts bon d'achat vouchers

Once the flag is enabled and the method is assigned to a POS configuration, the frontend is able to
pre-fill voucher payments automatically when the cashier selects that method.

### Distributing Vouchers

- Print vouchers from the Loyalty Cards list
- Send by email to selected customers
- Export codes for external distribution

## Usage in POS

### Applying a Bon d'achat

1. Open a POS session
2. Add products to the order
3. Click the **Bon d'achat** button in the control panel
4. Enter the voucher code when prompted
5. The system validates the voucher and adds an **informational line**:
   - Success message: "Bon d'achat [CODE] enregistré ([AMOUNT]). Sélectionnez le mode de paiement BON ACHAT lors du règlement."
   - An informational line appears in the order showing the voucher code and amount
   - **Important**: Order totals remain unchanged at this stage (no automatic discount applied)
   - Voucher metadata is stored internally for the payment phase

### Payment with BON ACHAT

1. After adding products and applying voucher codes, click **Payment**
2. In the payment screen, select the **BON ACHAT** payment method
3. The payment amount automatically pre-fills with the voucher value:
   - If voucher amount ≤ order total: Full voucher amount is used
   - If voucher amount > order total: Only the order total is used (remainder is lost)
4. Add additional payment methods if needed (for amounts exceeding voucher value)
5. Click **Validate** to complete the order

**Example workflows:**

- **Scenario A** (Voucher < Total): Order €100, voucher €50 → BON ACHAT payment €50 + Cash €50
- **Scenario B** (Voucher > Total): Order €30, voucher €50 → BON ACHAT payment €30 only (€20 forfeited)
- **Scenario C** (Multiple vouchers): Order €100, vouchers €30 + €40 → BON ACHAT payment €70 + Cash €30

### Validation Errors

The system will reject vouchers that are:

- Already used: "Ce bon d'achat a déjà été utilisé"
- Expired: "Ce bon d'achat a expiré"
- Invalid: "Ce code n'est pas un bon d'achat valide"
- From inactive programs: "Le programme de ce bon d'achat n'est plus actif"

### Receipt Display

The receipt shows:

- Order lines with subtotals
- Informational Bon d'achat line(s) indicating which voucher(s) were registered (€0.00 impact)
- Payment lines including BON ACHAT payment(s) with actual amounts redeemed
- Total paid and change (if any)

## Technical Details

### Module Structure

```text
pos_bon_achat/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── loyalty_program.py    # Program type extension
│   ├── loyalty_card.py        # State management
│   ├── pos_config.py          # POS configuration
│   └── pos_order.py           # Order validation
├── wizard/
│   ├── __init__.py
│   └── loyalty_generate_wizard.py
├── views/
│   ├── loyalty_program_views.xml
│   ├── loyalty_card_views.xml
│   └── loyalty_generate_wizard_views.xml
├── security/
│   └── ir.model.access.csv
└── static/src/
    └── app/
        ├── models/
        │   └── pos_order.js        # Frontend order logic
        ├── services/
        │   └── pos_store.js        # Code activation
        └── screens/
            └── product_screen/
                └── control_buttons/
                    ├── control_buttons.js   # Button logic
                    └── control_buttons.xml  # Button template
```

### Key Model Extensions

#### loyalty.program

- Adds `bon_achat` to program_type selection
- Enforces `limit_usage = True` and `max_usage = 1`
- Provides default values for bon d'achat programs

#### loyalty.card

- Adds `state` field (active, used, expired)
- Adds `source_pos_order_id` to track usage
- Adds `used_date` timestamp
- Implements `mark_bon_achat_as_used()` method

#### pos.order

- Overrides `validate_coupon_programs()` for bon_achat validation
- Overrides `confirm_coupon_programs()` to mark as used
- Creates usage history entries

### Frontend Components

#### PosStore (pos_store.js)

- `activateBonAchat(code)`: Validates and applies bon d'achat codes

#### PosOrder (pos_order.js)

- Overrides `_applyReward()` for single-use logic
- Ensures full consumption regardless of amount applied

#### ControlButtons (control_buttons.js/xml)

- Adds "Bon d'achat" button
- Opens code entry popup

## Security

Access rights are defined in `security/ir.model.access.csv`:

- **Users**: Read-only access to programs and cards
- **POS Users**: Can read and write loyalty cards
- **POS Managers**: Full access to programs and cards

## Compatibility

- **Odoo Version**: 19.0
- **Dependencies**:
  - `loyalty` (Coupons & Loyalty)
  - `pos_loyalty` (Point of Sale - Coupons & Loyalty)

## Known Limitations

1. Bon d'achat vouchers cannot be used in eCommerce (by design)
2. Once used, vouchers cannot be reactivated (by design)
3. Partial amounts are not refunded (by design)
4. Cannot combine multiple bon d'achat in a single order (standard Odoo behavior)

## Support

For issues or questions:

1. Check the system logs for detailed error messages
2. Verify the voucher state in the backend
3. Ensure the program is active and within validity dates

## License

LGPL-3

## Author

Custom development based on Odoo's loyalty framework

## Technical Notes

### POS Field Loading

The `pos_session.py` model extends the POS loader to ensure custom fields are available in the frontend:

```python
def _loader_params_pos_payment_method(self):
    result = super()._loader_params_pos_payment_method()
    result['search_params']['fields'].append('is_bon_achat_method')
    return result
```

This is **required** for any custom fields added to models loaded by POS. Without this, you'll encounter errors like:

```
OwlError: "pos.payment.method"."is_bon_achat_method" field is undefined
```

## Changelog

### Version 1.1 (2025-11-19)

- Added dedicated BON ACHAT payment method with auto-fill functionality
- Voucher entries now informational-only (no automatic discount application)
- Payment workflow: scan vouchers → select BON ACHAT payment → redeem
- Fixed POS field loader to properly load `is_bon_achat_method` field
- Fixed payment method visibility (active by default)

### Version 1.0

- Initial release
- Support for single-use bon d'achat vouchers
- POS-only restriction
- Full French language support
- Backend generation and management
- POS frontend integration
