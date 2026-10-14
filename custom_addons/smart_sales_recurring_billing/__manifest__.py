# -*- coding: utf-8 -*-
{
    'name': 'Smart Sales Quotation Builder & Recurring Subscription Billing',
    'version': '17.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Intelligent Quotation Builder with Margin Safeguards, Automated Recurring Invoices, ARR/MRR Metrics, and Payment Gateways.',
    'description': """
Smart Sales Quotation Builder & Recurring Subscription Billing
==============================================================
An enterprise-grade Odoo 17 module extending Sales, CRM, and Invoicing:

Key Features:
-------------
* **Smart Quotation Builder**:
  - Live margin and profitability diagnostics per quotation line.
  - Tier-based pricing rules (Standard, Enterprise, Strategic Partner).
  - High-discount validation guardrails requiring management approval.
  - Seamless one-click conversion from Sales Order to Recurring Contract.

* **Automated Recurring Invoices (Subscription Engine)**:
  - Multi-frequency cycles: Monthly (30 days), Quarterly (90 days), Annual (365 days).
  - Automated Cron scheduler (`ir.cron`) processing renewals and generating customer invoices.
  - Full lifecycle state machine: Draft -> Active -> Paused -> Closed/Expired.
  - Comprehensive revenue metrics: Monthly Recurring Revenue (MRR) and Annual Recurring Revenue (ARR).

* **CRM Opportunity Pipeline Integration**:
  - Track prospective MRR and ARR directly on CRM Leads & Opportunities.
  - 1-Click creation of Recurring Quotations from Won/Qualified Leads.

* **Payment Gateway & Automated Capture Simulator**:
  - Automated payment retry logic, transaction audit logging, and webhook event handling.
    """,
    'author': 'Hamza Ihsan',
    'website': 'https://talentpulse-ai-wci2.onrender.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'account',
        'crm',
        'mail',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/subscription_sequence.xml',
        'data/ir_cron_data.xml',
        'views/sale_order_views.xml',
        'views/recurring_subscription_views.xml',
        'views/crm_lead_views.xml',
        'views/payment_transaction_views.xml',
        'views/menus.xml',
        'reports/subscription_report_template.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
