# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestSmartSalesRecurringBilling(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestSmartSalesRecurringBilling, cls).setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Product = cls.env['product.product']
        cls.SaleOrder = cls.env['sale.order']
        cls.Subscription = cls.env['recurring.subscription']
        cls.CrmLead = cls.env['crm.lead']

        # Setup test customer
        cls.customer = cls.Partner.create({
            'name': 'Acme Enterprise Corp',
            'email': 'billing@acme-corp.com',
        })

        # Setup test SaaS service product
        cls.saas_product = cls.Product.create({
            'name': 'Cloud ERP Platform License (Monthly)',
            'type': 'service',
            'lst_price': 1000.0,
            'standard_price': 300.0,
        })

    def test_01_quotation_margin_and_discount_guardrail(self):
        """Verifies margin calculation and high-discount guardrail validation."""
        order = self.SaleOrder.create({
            'partner_id': self.customer.id,
            'is_subscription': True,
            'billing_cycle': 'monthly',
            'order_line': [
                (0, 0, {
                    'product_id': self.saas_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 1000.0,
                    'discount': 25.0, # Exceeds 20% limit
                })
            ]
        })

        # Verify discount approval requirement is triggered
        self.assertTrue(order.require_discount_approval)
        self.assertFalse(order.discount_approved)

        # Confirming without approval should raise ValidationError
        with self.assertRaises(ValidationError):
            order.action_confirm()

        # Approve discount and confirm
        order.discount_approved = True
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(order.subscription_id, "Linked subscription must be automatically created upon order confirmation.")
        self.assertEqual(order.subscription_id.stage, 'active')

    def test_02_mrr_arr_calculations(self):
        """Validates MRR and ARR computations across monthly, quarterly, and annual cycles."""
        # Monthly subscription: $1200 / month
        sub_monthly = self.Subscription.create({
            'partner_id': self.customer.id,
            'billing_cycle': 'monthly',
            'start_date': date(2026, 1, 1),
            'line_ids': [
                (0, 0, {
                    'product_id': self.saas_product.id,
                    'name': 'Monthly SaaS',
                    'quantity': 1,
                    'price_unit': 1200.0,
                    'discount': 0.0,
                })
            ]
        })
        self.assertEqual(sub_monthly.recurring_amount, 1200.0)
        self.assertEqual(sub_monthly.mrr, 1200.0)
        self.assertEqual(sub_monthly.arr, 14400.0)

        # Quarterly subscription: $3000 / quarter
        sub_quarterly = self.Subscription.create({
            'partner_id': self.customer.id,
            'billing_cycle': 'quarterly',
            'start_date': date(2026, 1, 1),
            'line_ids': [
                (0, 0, {
                    'product_id': self.saas_product.id,
                    'name': 'Quarterly SaaS',
                    'quantity': 1,
                    'price_unit': 3000.0,
                    'discount': 0.0,
                })
            ]
        })
        self.assertEqual(sub_quarterly.recurring_amount, 3000.0)
        self.assertEqual(sub_quarterly.mrr, 1000.0)
        self.assertEqual(sub_quarterly.arr, 12000.0)

        # Annual subscription: $12000 / year
        sub_annual = self.Subscription.create({
            'partner_id': self.customer.id,
            'billing_cycle': 'annually',
            'start_date': date(2026, 1, 1),
            'line_ids': [
                (0, 0, {
                    'product_id': self.saas_product.id,
                    'name': 'Annual SaaS',
                    'quantity': 1,
                    'price_unit': 12000.0,
                    'discount': 0.0,
                })
            ]
        })
        self.assertEqual(sub_annual.recurring_amount, 12000.0)
        self.assertEqual(sub_annual.mrr, 1000.0)
        self.assertEqual(sub_annual.arr, 12000.0)

    def test_03_recurring_invoice_generation_and_date_advance(self):
        """Verifies customer invoice generation, audit log, and date increment."""
        sub = self.Subscription.create({
            'partner_id': self.customer.id,
            'billing_cycle': 'monthly',
            'start_date': date(2026, 1, 1),
            'next_invoice_date': date(2026, 1, 1),
            'line_ids': [
                (0, 0, {
                    'product_id': self.saas_product.id,
                    'name': 'Monthly License',
                    'quantity': 2,
                    'price_unit': 500.0,
                    'discount': 10.0, # 2 * 500 * 0.9 = 900
                })
            ]
        })
        sub.action_activate()

        # Trigger invoice generation
        invoice = sub.generate_recurring_invoice()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.partner_id.id, self.customer.id)
        self.assertEqual(sub.next_invoice_date, date(2026, 2, 1), "Next billing date should advance by exactly 1 month.")
        self.assertEqual(sub.invoice_count, 1)

    def test_04_crm_lead_to_recurring_quotation(self):
        """Verifies CRM pipeline opportunity conversion to a recurring sales quote."""
        lead = self.CrmLead.create({
            'name': 'Enterprise Cloud Upgrade Deal',
            'partner_id': self.customer.id,
            'is_subscription_lead': True,
            'recurring_billing_cycle': 'annually',
            'expected_mrr': 5000.0,
        })
        self.assertEqual(lead.expected_arr, 60000.0, "Expected ARR must equal expected MRR * 12.")

        action = lead.action_create_recurring_quotation()
        sale_order = self.SaleOrder.browse(action['res_id'])
        self.assertTrue(sale_order.is_subscription)
        self.assertEqual(sale_order.billing_cycle, 'annually')
        self.assertEqual(sale_order.partner_id.id, self.customer.id)
