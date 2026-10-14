# -*- coding: utf-8 -*-
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class RecurringSubscription(models.Model):
    _name = 'recurring.subscription'
    _description = 'Recurring Subscription & Contract Engine'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string="Contract Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=True,
        tracking=True,
        help="Customer account bound to this recurring contract."
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string="Origin Quotation / Order",
        readonly=True,
        copy=False
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Account Executive",
        default=lambda self: self.env.user,
        tracking=True
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
        related='company_id.currency_id',
        readonly=True
    )
    stage = fields.Selection(
        selection=[
            ('draft', 'Draft Agreement'),
            ('active', 'Active & Billing'),
            ('paused', 'Paused / Hold'),
            ('closed', 'Completed / Expired'),
            ('cancelled', 'Cancelled'),
        ],
        string="Contract Stage",
        default='draft',
        required=True,
        copy=False,
        tracking=True
    )
    billing_cycle = fields.Selection(
        selection=[
            ('monthly', 'Monthly (30 Days)'),
            ('quarterly', 'Quarterly (90 Days)'),
            ('annually', 'Annual (365 Days)'),
        ],
        string="Billing Frequency",
        default='monthly',
        required=True,
        tracking=True
    )
    start_date = fields.Date(
        string="Start Date",
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    next_invoice_date = fields.Date(
        string="Next Invoice Date",
        copy=False,
        tracking=True,
        help="Date on which the next recurring customer invoice will be generated."
    )
    end_date = fields.Date(
        string="Expiration / End Date",
        help="Optional contract expiration date. Contract halts renewals after this date."
    )
    line_ids = fields.One2many(
        comodel_name='recurring.subscription.line',
        inverse_name='subscription_id',
        string="Contract Lines",
        copy=True
    )
    recurring_amount = fields.Monetary(
        string="Billing Amount per Cycle",
        compute='_compute_revenue_metrics',
        store=True,
        currency_field='currency_id',
        help="Sum of contract lines billed each cycle."
    )
    mrr = fields.Monetary(
        string="Monthly Recurring Revenue (MRR)",
        compute='_compute_revenue_metrics',
        store=True,
        currency_field='currency_id',
        help="Normalized revenue earned per 30-day period."
    )
    arr = fields.Monetary(
        string="Annual Recurring Revenue (ARR)",
        compute='_compute_revenue_metrics',
        store=True,
        currency_field='currency_id',
        help="Annualized projected value of this contract."
    )
    invoice_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='subscription_id',
        string="Generated Invoices",
        readonly=True
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute='_compute_invoice_count',
        store=False
    )
    auto_debit = fields.Boolean(
        string="Auto-Debit Payment",
        default=True,
        help="Attempt automated payment capture immediately after invoice creation."
    )
    payment_status = fields.Selection(
        selection=[
            ('pending', 'Pending Invoicing'),
            ('paid', 'Current & Paid'),
            ('overdue', 'Payment Past Due'),
        ],
        string="Payment Standing",
        default='pending',
        tracking=True
    )
    notes = fields.Html(
        string="Contract Terms & Notes"
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('recurring.subscription') or _('New')
        return super(RecurringSubscription, self).create(vals)

    @api.depends('line_ids.subtotal', 'billing_cycle')
    def _compute_revenue_metrics(self):
        for sub in self:
            total_cycle = sum(line.subtotal for line in sub.line_ids)
            sub.recurring_amount = total_cycle
            if sub.billing_cycle == 'monthly':
                sub.mrr = total_cycle
                sub.arr = total_cycle * 12.0
            elif sub.billing_cycle == 'quarterly':
                sub.mrr = total_cycle / 3.0
                sub.arr = (total_cycle / 3.0) * 12.0
            elif sub.billing_cycle == 'annually':
                sub.mrr = total_cycle / 12.0
                sub.arr = total_cycle
            else:
                sub.mrr = total_cycle
                sub.arr = total_cycle * 12.0

    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    def action_activate(self):
        """Activates contract and sets initial next_invoice_date."""
        for sub in self:
            if not sub.line_ids:
                raise UserError(_("Cannot activate subscription '%s' with no products or service lines.") % sub.name)
            sub.stage = 'active'
            if not sub.next_invoice_date:
                sub.next_invoice_date = sub.start_date or fields.Date.today()
            sub.payment_status = 'pending'
            sub.message_post(body=_("Subscription activated. Next billing run scheduled for: %s") % sub.next_invoice_date)

    def action_pause(self):
        """Pauses recurring billing."""
        self.write({'stage': 'paused'})
        self.message_post(body=_("Subscription billing temporarily paused."))

    def action_resume(self):
        """Resumes recurring billing."""
        today = fields.Date.today()
        for sub in self:
            vals = {'stage': 'active'}
            if sub.next_invoice_date < today:
                vals['next_invoice_date'] = today
            sub.write(vals)
            sub.message_post(body=_("Subscription resumed. Next invoice date: %s") % sub.next_invoice_date)

    def action_close(self):
        """Marks contract as expired/completed."""
        self.write({'stage': 'closed'})
        self.message_post(body=_("Subscription contract marked as completed / closed."))

    def action_cancel(self):
        """Cancels contract."""
        self.write({'stage': 'cancelled'})
        self.message_post(body=_("Subscription contract cancelled."))

    def _compute_next_billing_date(self, current_date):
        """Calculates next billing date based on cycle frequency."""
        if self.billing_cycle == 'monthly':
            return current_date + relativedelta(months=1)
        elif self.billing_cycle == 'quarterly':
            return current_date + relativedelta(months=3)
        elif self.billing_cycle == 'annually':
            return current_date + relativedelta(years=1)
        return current_date + relativedelta(months=1)

    def generate_recurring_invoice(self):
        """
        Generates customer invoice (account.move) for this subscription,
        moves next_invoice_date forward, and logs transaction audit.
        """
        self.ensure_one()
        if self.stage != 'active':
            raise UserError(_("Cannot generate invoice for inactive subscription '%s'.") % self.name)

        if not self.line_ids:
            raise UserError(_("Subscription '%s' has no contract lines.") % self.name)

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'invoice_date': fields.Date.today(),
            'subscription_id': self.id,
            'narration': _("Recurring Invoice for contract %s (%s cycle)") % (self.name, self.billing_cycle),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.display_name,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                }) for line in self.line_ids
            ]
        }

        invoice = self.env['account.move'].create(invoice_vals)

        # Advance next billing date
        base_date = self.next_invoice_date or fields.Date.today()
        new_next_date = self._compute_next_billing_date(base_date)

        # Check for expiration
        if self.end_date and new_next_date > self.end_date:
            self.write({
                'stage': 'closed',
                'next_invoice_date': False,
                'payment_status': 'paid'
            })
            self.message_post(body=_("Contract reached end date %s and was auto-closed.") % self.end_date)
        else:
            self.write({
                'next_invoice_date': new_next_date,
                'payment_status': 'paid'
            })

        # Record payment transaction audit log
        self.env['subscription.payment.log'].create({
            'subscription_id': self.id,
            'invoice_id': invoice.id,
            'amount': invoice.amount_total,
            'currency_id': self.currency_id.id,
            'status': 'success',
            'gateway_reference': f"AUTO_SIM_{invoice.id}_{fields.Date.today().strftime('%Y%m%d')}",
            'notes': _("Automated recurring billing cycle processed successfully.")
        })

        self.message_post(body=_("Generated Recurring Invoice: <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>. Next billing: %s") % (
            invoice.id, invoice.name or invoice.id, self.next_invoice_date
        ))

        return invoice

    @api.model
    def _cron_process_recurring_invoices(self):
        """
        Scheduled Action (Daily Cron):
        Identifies active subscriptions where next_invoice_date <= today and creates invoices.
        """
        today = fields.Date.today()
        due_subscriptions = self.search([
            ('stage', '=', 'active'),
            ('next_invoice_date', '<=', today)
        ])

        created_invoices = []
        for sub in due_subscriptions:
            try:
                inv = sub.generate_recurring_invoice()
                created_invoices.append(inv.id)
            except Exception as e:
                sub.write({'payment_status': 'overdue'})
                sub.message_post(body=_("Automated recurring billing failed: %s") % str(e))

        return len(created_invoices)

    def action_view_invoices(self):
        """Opens related invoices list."""
        self.ensure_one()
        return {
            'name': _('Subscription Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id, 'default_move_type': 'out_invoice'},
        }


class RecurringSubscriptionLine(models.Model):
    _name = 'recurring.subscription.line'
    _description = 'Recurring Subscription Line Item'

    subscription_id = fields.Many2one(
        comodel_name='recurring.subscription',
        string="Subscription",
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Service / Product",
        required=True
    )
    name = fields.Text(
        string="Description",
        required=True
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        digits='Product Unit of Measure'
    )
    price_unit = fields.Float(
        string="Unit Price",
        digits='Product Price'
    )
    discount = fields.Float(
        string="Discount (%)",
        default=0.0
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        related='subscription_id.currency_id',
        string="Currency",
        readonly=True
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.get_product_multiline_description_sale()
            self.price_unit = self.product_id.lst_price

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_subtotal(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.subtotal = line.quantity * price


class AccountMove(models.Model):
    _inherit = 'account.move'

    subscription_id = fields.Many2one(
        comodel_name='recurring.subscription',
        string="Source Subscription",
        readonly=True,
        copy=False,
        help="Linked recurring subscription from which this invoice was generated."
    )
