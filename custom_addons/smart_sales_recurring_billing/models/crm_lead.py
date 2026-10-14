# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_subscription_lead = fields.Boolean(
        string="Recurring Revenue Deal",
        default=False,
        help="Mark if this opportunity involves monthly or annual recurring SaaS / service billing."
    )
    recurring_billing_cycle = fields.Selection(
        selection=[
            ('monthly', 'Monthly (30 Days)'),
            ('quarterly', 'Quarterly (90 Days)'),
            ('annually', 'Annual (365 Days)'),
        ],
        string="Target Billing Cycle",
        default='monthly'
    )
    expected_mrr = fields.Monetary(
        string="Expected MRR",
        currency_field='company_currency',
        help="Estimated Monthly Recurring Revenue from this customer."
    )
    expected_arr = fields.Monetary(
        string="Expected ARR",
        compute='_compute_expected_arr',
        store=True,
        currency_field='company_currency',
        help="Annualized Recurring Revenue projected from this deal."
    )

    @api.depends('expected_mrr')
    def _compute_expected_arr(self):
        for lead in self:
            lead.expected_arr = (lead.expected_mrr or 0.0) * 12.0

    def action_create_recurring_quotation(self):
        """Generates a pre-configured recurring Sales Quotation directly from CRM opportunity."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please assign or create a customer contact before generating a quotation."))

        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'opportunity_id': self.id,
            'team_id': self.team_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'user_id': self.user_id.id or self.env.uid,
            'is_subscription': True,
            'billing_cycle': self.recurring_billing_cycle or 'monthly',
        })

        self.message_post(body=_("Created recurring sales quotation: <a href=# data-oe-model=sale.order data-oe-id=%d>%s</a>") % (
            sale_order.id, sale_order.name
        ))

        return {
            'name': _('Recurring Sales Quotation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': sale_order.id,
            'target': 'current',
        }
