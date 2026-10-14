# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _


class SubscriptionPaymentLog(models.Model):
    _name = 'subscription.payment.log'
    _description = 'Subscription Payment & Gateway Audit Trail'
    _order = 'create_date desc'

    subscription_id = fields.Many2one(
        comodel_name='recurring.subscription',
        string="Subscription",
        required=True,
        ondelete='cascade'
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string="Invoice",
        ondelete='set null'
    )
    transaction_uuid = fields.Char(
        string="Idempotency Key",
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False
    )
    gateway_reference = fields.Char(
        string="Gateway Reference",
        help="External payment gateway charge ID (Stripe, PayPal, Bank API)."
    )
    amount = fields.Monetary(
        string="Charged Amount",
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending Processing'),
            ('success', 'Charge Captured'),
            ('failed', 'Card Declined / Error'),
            ('refunded', 'Refunded'),
        ],
        string="Payment Status",
        default='pending',
        required=True
    )
    error_message = fields.Text(
        string="Gateway Error Diagnostics"
    )
    notes = fields.Char(
        string="Transaction Notes"
    )

    def action_retry_charge(self):
        """Simulates re-executing credit card or mandate capture with external gateway."""
        for log in self:
            # Simulate successful webhook response
            log.status = 'success'
            log.gateway_reference = f"RETRY_AUTH_{log.id}_{fields.Date.today().strftime('%Y%m%d%H%M')}"
            log.error_message = False
            if log.subscription_id:
                log.subscription_id.payment_status = 'paid'
                log.subscription_id.message_post(body=_("Payment re-capture succeeded via Gateway Reference: %s") % log.gateway_reference)
