# Custom Supplier Approval Module

## 📋 Overview

**Custom Supplier Approval** is a comprehensive Odoo 19 module for managing the complete supplier lifecycle, from initial approval requests through ongoing performance evaluation. It provides structured workflows, automated notifications, performance tracking, and rich analytics to help organizations maintain high-quality supplier relationships.

## ✨ Key Features

### 🔐 Supplier Approval Workflow

- **Multi-state workflow**: Draft → Pending → Approved/Rejected
- **Role-based approval**: Purchase users submit, managers approve/reject
- **Legal document tracking**: Attach and monitor supplier certifications, insurance, contracts
- **Document expiration monitoring**: Automatic alerts for expiring documents
- **Activity management**: Automated task creation for approvers

### 📊 Supplier Evaluation System

- **5-criteria assessment**: Quality (30%), Delivery (25%), Reactivity (20%), Compliance (15%), Relationship (10%)
- **Weighted scoring**: Automatic calculation of overall performance score
- **Purchase order integration**: Link evaluations to specific POs
- **Historical tracking**: Monitor supplier performance evolution over time
- **Evaluation wizard**: Quick evaluation from purchase order form

### 📧 Email Notifications

- **Submission alerts**: Notify managers of new approval requests
- **Approval/rejection confirmation**: Inform requesters of decisions
- **Evaluation reminders**: Prompt users to evaluate suppliers after PO completion
- **Professional HTML templates**: Branded, mobile-responsive emails

### 🤖 Automation

- **Automated activities**: Create evaluation tasks 7 days after PO confirmation
- **Performance alerts**: Notify managers of 3 consecutive poor evaluations (<50%)
- **Document expiration checks**: Daily cron job monitoring legal document validity
- **Evaluation reminders**: Monthly cron job for POs >30 days without evaluation

### 📈 Analytics & Reporting

- **Dashboard**: KPI tiles showing approved suppliers, pending requests, average scores
- **Pivot analysis**: Multi-dimensional analysis by supplier, period, evaluator
- **Graph views**: Score evolution (line chart), request distribution (pie chart), criteria comparison (bar chart)
- **PDF Reports**:
  - **Approval Request Report**: QR code, supplier details, legal documents table
  - **Evaluation Report**: Radar chart visualization, weighted scores, detailed criteria
  - **Performance Report**: Statistics, PO history, trend analysis, criteria averages

### 🔒 Security

- **Access control**: Separate permissions for purchase users and managers
- **Record rules**: Users can only edit their own draft requests
- **Audit trail**: Complete tracking via mail.thread integration

---

## 📦 Installation

### Prerequisites

- **Odoo Version**: 19.0 Community or Enterprise
- **Required Dependencies**:
  - `purchase` (Purchase Management)
  - `mail` (Discuss - Email & Messaging)
  - `base_automation` (Automation Rules) ⚠️ **Must install first**

### Installation Steps

1. **Install base_automation module FIRST** (Required):
   - Go to **Apps** menu
   - Remove the "Apps" filter
   - Search for **"automation"** or **"Automation Rules"**
   - Click **Install** on "Automation Rules" module
   - Wait for installation to complete

2. **Copy module to addons directory**:

   ```bash
   cp -r custom_supplier_approval /path/to/odoo/server/addons/
   ```

3. **Update apps list**:

   ```bash
   # Via command line
   python odoo-bin -c odoo.conf -d DATABASE_NAME -u all --stop-after-init
   
   # Or in Odoo: Apps > Update Apps List
   ```

4. **Install the module**:
   - Go to **Apps**
   - Search for "Supplier Approval"
   - Click **Install**

5. **Configure users**:
   - Assign users to **Purchase / User** group for basic access
   - Assign users to **Purchase / Manager** group for approval rights

---

## 🚀 Usage Guide

### For Purchase Users

#### 1. Create a Supplier Approval Request

1. Navigate to **Suppliers > Approval Requests**
2. Click **Create**
3. Fill in the form:
   - **Supplier**: Select or create supplier
   - **Services Provided**: Describe supplier offerings
   - **Legal Documents**: Add required certifications (Insurance, Tax, Business License, etc.)
     - Document Type
     - Document Number
     - Issue Date & Expiry Date
4. **Save** (Draft state)
5. Click **Submit for Approval** button

**What happens:**

- State changes to "Pending"
- Email sent to all Purchase Managers
- Activity created for managers to review

#### 2. Evaluate a Supplier (After PO)

**Option A: From Purchase Order**

1. Open confirmed purchase order
2. Click **Evaluate Supplier** button
3. Fill in the wizard:
   - Quality Score (0-100)
   - Delivery Score (0-100)
   - Reactivity Score (0-100)
   - Compliance Score (0-100)
   - Relationship Score (0-100)
   - Comments (optional)
4. Click **Validate**

**Option B: Manually**

1. Navigate to **Suppliers > Evaluations**
2. Click **Create**
3. Select supplier and optionally link to PO
4. Enter scores and comments
5. **Save** - Overall score computed automatically

**Overall Score Formula:**

```
Overall = (Quality × 30%) + (Delivery × 25%) + (Reactivity × 20%) + 
          (Compliance × 15%) + (Relationship × 10%)
```

### For Purchase Managers

#### 1. Approve/Reject Requests

1. Navigate to **Suppliers > Approval Requests**
2. Filter by **Pending** state
3. Open a request to review:
   - Supplier information
   - Legal documents (check expiry dates)
   - Services provided
4. Decision:
   - **Approve**: Click **Approve** button → Requester notified via email
   - **Reject**: Enter **Rejection Reason** → Click **Reject** → Requester notified

#### 2. Monitor Performance Alerts

1. Check **Activities** for:
   - 🔴 **Performance Alerts**: Suppliers with 3 consecutive scores <50%
   - ⚠️ **Expired Documents**: Legal documents past expiry date
   - 📅 **Evaluation Reminders**: POs awaiting supplier evaluation

2. Take action:
   - Review supplier relationship
   - Contact supplier for corrective measures
   - Request updated legal documents

### Analytics & Dashboards

#### 1. Dashboard Overview

- Navigate to **Suppliers > 📊 Tableau de Bord**
- View KPIs:
  - Approved Suppliers Count
  - Pending Requests
  - Average Score
  - Monthly Evaluations
- Click any metric to drill down to detailed list

#### 2. Pivot Analysis

- Navigate to **Suppliers > Reports > Analyse Pivot**
- Default view: Suppliers (rows) × Months (columns) × Average Score
- Customize:
  - Add evaluator dimension
  - Group by quarter/year
  - Filter by score ranges (excellent/good/poor)
- Export to Excel for further analysis

#### 3. Graph Views

- **Score Evolution**: Line chart showing performance trends over months
- **Request Distribution**: Pie chart of approval states
- **Criteria Comparison**: Bar chart comparing supplier scores by criterion

#### 4. PDF Reports

- Open any approval request or evaluation
- Click **Print** dropdown
- Select:
  - **Approval Request Report**: Full details with QR code
  - **Evaluation Report**: Radar chart with detailed scores
  - **Performance Report**: Historical statistics and trends

---

## ⚙️ Configuration

### Email Templates

Email templates can be customized via:
**Settings > Technical > Email > Templates**

- `mail_template_approval_request_submitted`
- `mail_template_approval_request_approved`
- `mail_template_approval_request_rejected`
- `mail_template_evaluation_reminder`

**Customizable elements:**

- Subject lines
- Email body HTML
- Recipients
- Attached documents

### Automated Actions

Modify automation behavior via:
**Settings > Technical > Automation > Automated Actions**

- **Create Evaluation Activity on PO Confirmation**: Adjust deadline (default 7 days)
- **Performance Alert on 3 Bad Evaluations**: Change threshold or consecutive count

### Cron Jobs

Configure scheduled actions via:
**Settings > Technical > Automation > Scheduled Actions**

- **Check Expired Legal Documents**: Default daily at midnight
- **Send Evaluation Reminders**: Default monthly

**Adjustable parameters:**

- Frequency (days/weeks/months)
- Execution time
- Active/inactive state

### Score Thresholds

Modify color-coded thresholds in code (for advanced users):

- **Green** (Excellent): ≥75%
- **Yellow** (Good): 50-74%
- **Red** (Poor): <50%

Edit files: `supplier_approval_report.xml`, `supplier_evaluation_report.xml`

---

## 🧪 Testing

### Run All Tests

```bash
python odoo-bin -c odoo.conf -d test_db -i custom_supplier_approval --test-enable --stop-after-init
```

### Test Coverage

- **Workflow Tests**: `test_supplier_approval_request.py` (12 test cases)
  - State transitions, validation constraints, permission checks
- **Evaluation Tests**: `test_supplier_evaluation.py` (12 test cases)
  - Score calculations, weighted averages, date validations
- **Integration Tests**: `test_purchase_integration.py` (10 test cases)
  - PO domain filters, evaluation wizard, smart buttons
- **Security Tests**: `test_security.py` (15 test cases)
  - ACL rules, record rules, role-based access

### Running Specific Tests

```bash
# Run only workflow tests
python odoo-bin -c odoo.conf -d test_db --test-enable --test-tags=supplier_approval -i custom_supplier_approval --stop-after-init

# Run with verbose output
python odoo-bin -c odoo.conf -d test_db --test-enable --log-level=test -i custom_supplier_approval --stop-after-init
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. **Email notifications not sending**

**Symptoms**: Users don't receive approval/rejection emails

**Solutions**:

- Check **Settings > Technical > Email > Outgoing Mail Servers**
- Verify SMTP configuration is correct
- Test email server connection
- Check spam folders
- Review email template recipient fields

#### 2. **Automated actions not triggering**

**Symptoms**: No evaluation activities created after PO confirmation

**Solutions**:

- Verify automated action is **Active**: Settings > Technical > Automation > Automated Actions
- Check domain filter matches PO state correctly
- Ensure user has proper permissions
- Review server logs for errors

#### 3. **Cron jobs not running**

**Symptoms**: Expired documents not marked, no reminders sent

**Solutions**:

- Check cron is enabled in Odoo configuration
- Verify scheduled action is **Active**: Settings > Technical > Automation > Scheduled Actions
- Check "Next Execution Date" field
- Run manually: Click "Run Manually" button to test

#### 4. **Pivot view shows no data**

**Symptoms**: Empty pivot table despite having evaluations

**Solutions**:

- Remove all filters in search bar
- Check date range filters
- Ensure evaluations exist: Suppliers > Evaluations
- Refresh browser cache

#### 5. **Permission errors when approving**

**Symptoms**: "Access Error" when clicking Approve button

**Solutions**:

- Verify user is in **Purchase / Manager** group: Settings > Users & Companies > Users
- Check record rules are properly configured: Settings > Technical > Security > Record Rules
- Review ACL definitions: Settings > Technical > Security > Access Rights

#### 6. **Overall score not calculating**

**Symptoms**: Overall score shows 0 or incorrect value

**Solutions**:

- Ensure all 5 criteria scores are entered (Quality, Delivery, Reactivity, Compliance, Relationship)
- Check scores are within 0-100 range
- Trigger recomputation: Edit evaluation and save
- Review compute method in `supplier_evaluation.py` line 80-85

#### 7. **Legal documents not showing in report**

**Symptoms**: PDF report missing legal documents table

**Solutions**:

- Ensure documents are linked to approval request (check `legal_document_ids`)
- Verify document records exist in database
- Check report template: `report/supplier_approval_report.xml` lines 100-127
- Regenerate report after adding documents

---

## 🗂️ Module Structure

```
custom_supplier_approval/
├── __init__.py
├── __manifest__.py
├── data/
│   ├── mail_template_approval_request.xml     (Email templates)
│   ├── supplier_approval_automated_actions.xml (Automated actions)
│   └── supplier_approval_cron.xml             (Scheduled actions)
├── models/
│   ├── __init__.py
│   ├── supplier_approval_request.py           (Main approval workflow)
│   ├── supplier_evaluation.py                 (Evaluation model)
│   ├── supplier_legal_document.py             (Legal documents)
│   └── purchase_order.py                      (PO integration)
├── views/
│   ├── supplier_approval_menus.xml            (Menu structure)
│   ├── supplier_approval_request_views.xml    (Form, tree, search views)
│   ├── supplier_evaluation_views.xml          (Evaluation views)
│   ├── supplier_legal_document_views.xml      (Document views)
│   ├── supplier_evaluation_pivot_view.xml     (Pivot analysis)
│   ├── supplier_evaluation_graph_views.xml    (Charts: line, pie, bar)
│   └── supplier_dashboard.xml                 (Dashboard with KPIs)
├── report/
│   ├── supplier_approval_report.xml           (Approval PDF with QR code)
│   ├── supplier_evaluation_report.xml         (Evaluation PDF with radar chart)
│   └── supplier_performance_report.xml        (Performance PDF with trends)
├── security/
│   ├── ir.model.access.csv                    (ACL definitions)
│   └── supplier_approval_security.xml         (Record rules)
├── wizards/
│   ├── __init__.py
│   └── supplier_evaluation_wizard.py          (Quick evaluation from PO)
├── tests/
│   ├── __init__.py
│   ├── test_supplier_approval_request.py      (Workflow tests)
│   ├── test_supplier_evaluation.py            (Score calculation tests)
│   ├── test_purchase_integration.py           (PO integration tests)
│   └── test_security.py                       (Security & permissions tests)
└── static/
    └── description/
        ├── icon.png                            (Module icon)
        ├── index.html                          (App store description)
        └── screenshots/                        (Feature screenshots)
```

---

## 📚 FAQ

**Q: Can I customize the approval workflow to add more states?**  
A: Yes, modify the `state` field in `supplier_approval_request.py` and add corresponding workflow methods.

**Q: Can I change the evaluation criteria weights?**  
A: Yes, edit the `_compute_overall_score` method in `supplier_evaluation.py` to adjust percentages.

**Q: How do I export evaluation data to Excel?**  
A: Use the Pivot View (Suppliers > Reports > Analyse Pivot), configure your analysis, then click the export button.

**Q: Can I disable automated emails?**  
A: Yes, go to Settings > Technical > Email > Templates and deactivate the specific template.

**Q: How do I add custom fields to the approval request?**  
A: Inherit `supplier.approval.request` model in a custom module, add fields, and extend the form view using XPath.

**Q: Can I integrate this with external systems?**  
A: Yes, the module provides standard Odoo ORM API access. Use XML-RPC or JSON-RPC to integrate.

---

## 🤝 Support & Contribution

### Reporting Issues

Please report bugs or feature requests via:

- **Email**: <support@yourcompany.com>
- **Issue Tracker**: [Your GitHub/GitLab repo URL]

### Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

### Coding Standards

- Follow Odoo coding guidelines
- Use `pylint-odoo` for linting
- Write comprehensive docstrings
- Add test coverage for new features

---

## 📄 License

This module is licensed under **LGPL-3** (GNU Lesser General Public License v3.0).

---

## 👥 Credits

**Author**: [Your Company Name]  
**Website**: [Your Website URL]  
**Version**: 1.0.0  
**Odoo Version**: 19.0  

**Contributors**:

- Your Name - Initial development
- [Additional contributors]

---

## 🔄 Changelog

### Version 1.0.0 (2024-XX-XX)

- Initial release
- Supplier approval workflow with legal document tracking
- 5-criteria evaluation system with weighted scoring
- Email notifications for workflow events
- Automated activities and performance alerts
- Document expiration monitoring
- Comprehensive analytics (pivot, graphs, dashboard)
- PDF reports with QR codes and radar charts
- Full test coverage (49 test cases)
- Security rules for purchase users and managers

---

**For additional help, please contact your Odoo administrator or refer to the official Odoo documentation.**
