# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_subscription = fields.Boolean(
        string="Recurring Subscription Order",
        default=False,
        help="Check this box to automatically generate a recurring billing contract upon order confirmation."
    )
    billing_cycle = fields.Selection(
        selection=[
            ('monthly', 'Monthly (30 Days)'),
            ('quarterly', 'Quarterly (90 Days)'),
            ('annually', 'Annual (365 Days)'),
        ],
        string="Billing Frequency",
        default='monthly',
        help="Frequency at which automatic invoices will be generated."
    )
    subscription_id = fields.Many2one(
        comodel_name='recurring.subscription',
        string="Linked Subscription",
        readonly=True,
        copy=False,
        help="Subscription contract generated from this quotation."
    )
    pricing_tier = fields.Selection(
        selection=[
            ('standard', 'Standard Tier'),
            ('enterprise', 'Enterprise Tier (10% Tier Discount)'),
            ('strategic', 'Strategic Partner (20% Tier Discount)'),
        ],
        string="Quotation Tier",
        default='standard',
        tracking=True,
        help="Select pricing tier to apply automatic volume discount baselines."
    )
    total_cost_amount = fields.Monetary(
        string="Estimated Cost Basis",
        compute='_compute_margin_diagnostics',
        currency_field='currency_id',
        store=True,
        help="Aggregated product standard costs."
    )
    profit_margin_pct = fields.Float(
        string="Profit Margin (%)",
        compute='_compute_margin_diagnostics',
        store=True,
        digits=(16, 2),
        help="Overall gross profit margin on this quotation."
    )
    require_discount_approval = fields.Boolean(
        string="Requires Manager Approval",
        compute='_compute_discount_approval',
        store=True,
        help="True if any line discount exceeds the 20% guardrail."
    )
    discount_approved = fields.Boolean(
        string="Manager Approved Discount",
        default=False,
        copy=False,
        tracking=True,
        help="Checked by a Sales Manager to permit confirmation of high-discount quotations."
    )

    @api.depends('order_line.price_subtotal', 'order_line.product_id')
    def _compute_margin_diagnostics(self):
        for order in self:
            total_cost = 0.0
            for line in order.order_line:
                cost = line.product_id.standard_price if line.product_id else 0.0
                total_cost += cost * line.product_uom_qty
            order.total_cost_amount = total_cost
            if order.amount_untaxed > 0:
                profit = order.amount_untaxed - total_cost
                order.profit_margin_pct = (profit / order.amount_untaxed) * 100.0
            else:
                order.profit_margin_pct = 0.0

    @api.depends('order_line.discount')
    def _compute_discount_approval(self):
        for order in self:
            order.require_discount_approval = any(line.discount > 20.0 for line in order.order_line)

    @api.onchange('pricing_tier')
    def _onchange_pricing_tier(self):
        """Applies tier-based discount rules across lines."""
        tier_discounts = {
            'standard': 0.0,
            'enterprise': 10.0,
            'strategic': 20.0,
        }
        discount = tier_discounts.get(self.pricing_tier, 0.0)
        for line in self.order_line:
            if discount > line.discount:
                line.discount = discount

    def action_approve_high_discount(self):
        """Allows authorized sales manager to approve quotation discounts > 20%."""
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_("Only Sales Managers are authorized to approve quotes with discounts exceeding 20%."))
        self.discount_approved = True
        self.message_post(body=_("High discount approved by manager: %s") % self.env.user.name)

    def action_confirm(self):
        """Enforces guardrails and creates recurring subscription upon order confirmation."""
        for order in self:
            if order.require_discount_approval and not order.discount_approved:
                raise ValidationError(_(
                    "Order %s cannot be confirmed because it contains line discounts exceeding 20%% "
                    "without manager approval. Please request approval first."
                ) % order.name)

        res = super(SaleOrder, self).action_confirm()

        for order in self:
            if order.is_subscription and not order.subscription_id:
                order._create_recurring_subscription()

        return res

    def _create_recurring_subscription(self):
        """Instantiates a linked recurring.subscription record."""
        self.ensure_one()
        sub_vals = {
            'partner_id': self.partner_id.id,
            'sale_order_id': self.id,
            'user_id': self.user_id.id or self.env.uid,
            'company_id': self.company_id.id,
            'billing_cycle': self.billing_cycle,
            'start_date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                }) for line in self.order_line if line.product_id
            ]
        }
        subscription = self.env['recurring.subscription'].create(sub_vals)
        self.subscription_id = subscription.id
        subscription.action_activate()
        self.message_post(body=_("Recurring Subscription created: <a href=# data-oe-model=recurring.subscription data-oe-id=%d>%s</a>") % (
            subscription.id, subscription.name
        ))
        return subscription

    def action_view_subscription(self):
        """Action button to navigate directly to the linked subscription."""
        self.ensure_one()
        return {
            'name': _('Subscription Contract'),
            'type': 'ir.actions.act_window',
            'res_model': 'recurring.subscription',
            'view_mode': 'form',
            'res_id': self.subscription_id.id,
            'target': 'current',
        }
