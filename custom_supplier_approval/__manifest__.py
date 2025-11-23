# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Supplier Approval & Evaluation",
    'version': '1.0',
    'category': 'Purchases',
    'images': [
        'static/description/icon.png',
        'static/description/screenshots/approval_workflow.png',
        'static/description/screenshots/evaluation_form.png',
        'static/description/screenshots/dashboard_insights.png',
        'static/description/screenshots/reports_bundle.png',
    ],
    'sequence': 10,
    'summary': "Manage supplier approval workflow and evaluation system",
    'description': """
        Supplier Approval & Evaluation Management
        ==========================================
        
        This module provides a complete supplier lifecycle management system:
        
        Key Features:
        -------------
        * Structured supplier registration with legal documents (RCCM, NCC, CNPS, etc.)
        * Approval workflow with validation circuit (Pending → Approved/Rejected)
        * Restrict purchases to approved suppliers only
        * Continuous supplier evaluation based on 5 objective criteria:
          - Quality of products/services
          - Delivery time compliance
          - Reactivity
          - Administrative compliance
          - Commercial relationship
        * Automatic satisfaction rate calculation (0-100 score)
        * Dashboard and analytics for supplier performance tracking
        * Email notifications and activity management
        * Full French language support
    """,
    'depends': ['base', 'purchase', 'mail', 'base_automation'],
    'data': [
        # Security
        'security/supplier_approval_groups.xml',
        'security/ir.model.access.csv',
        'security/supplier_approval_security.xml',
        
        # Data
        'data/supplier_approval_sequence.xml',
        'data/supplier_category_data.xml',
        'data/mail_template_approval_request.xml',
        'data/supplier_approval_automated_actions.xml',
        'data/supplier_approval_cron.xml',
        
        # Views
        'views/supplier_category_views.xml',
        'views/supplier_legal_document_views.xml',
        'views/res_partner_views.xml',
        'views/supplier_approval_request_views.xml',
        'views/supplier_evaluation_views.xml',
        'views/purchase_order_views.xml',
        'views/supplier_approval_menus.xml',
        'views/supplier_dashboard.xml',
        'views/supplier_evaluation_pivot_view.xml',
        'views/supplier_evaluation_graph_views.xml',
        
        # Wizards
        'wizards/supplier_evaluation_wizard_views.xml',
        'wizards/supplier_approval_bulk_wizard_views.xml',
        
        # Reports
        'report/supplier_approval_report.xml',
        'report/supplier_evaluation_report.xml',
        'report/supplier_performance_report.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
