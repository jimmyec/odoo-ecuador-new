# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api#, _
from odoo.exceptions import Warning as UserError
        
class PosRefundCredit(models.Model):
    _inherit = 'res.partner'

    @api.one
    def compute_refund_credit(self):
        """
        Metodo ...
        """
        self.refund_credit = 0
        refund_invoices = self.env['account.invoice'].search([('partner_id.id','=',self.id),('type','=','out_refund')])
        for refund_invoice in refund_invoices:
            self.refund_credit += refund_invoice.amount_total
        credit_invoices = self.env['account.invoice'].search([('partner_id.id','=',self.id),('type','=','out_invoice'),('state','=','open')])
        for credit_invoice in credit_invoices:
            for payment_line_id in credit_invoice.pos_payment_line_ids:
                if payment_line_id.journal_id.code == 'NCRD':
                    self.refund_credit -= float(payment_line_id.payment_amount)
        credit_payments = self.env['account.payment'].search([('partner_id.id','=',self.id),('payment_type','=','outbound')])
        for credit_payment in credit_payments:
            self.refund_credit -= float(credit_payment.amount)

    refund_credit = fields.Monetary(
        string='Credito',
        compute='compute_refund_credit',
        store=True,
        help='Crédito en Devoluciones o Notas de Crédito',
    )

class ProductCat(models.Model):
    """docstring for ProductCat"""
    _inherit = 'product.category'
    
    property_account_refund_categ_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta de devoluciones',
    )

class ProductTemp(models.Model):
    """docstring for ProductCat"""
    _inherit = 'product.template'
    
    property_account_product_refund_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta de devoluciones',
    )

class PosOrder(models.Model):
    """docstring for PosOrder"""
    _inherit = 'pos.order'

    _logger = logging.getLogger('pos.order')
    
    returned_order_id = fields.Many2one(
        comodel_name='pos.order',
        string='Returned Order',
        readonly=True,
    )
    order_type = fields.Selection(
        [
            ('sale','Orden de Venta'),
            ('refund','Orden de Devolución')
        ],
        string='Orden',
        readonly=True,
        default='sale'
        )
    returned = fields.Boolean(
        string='Retornado',
        readonly=True,)

    def refund(self):
        # Call super to use original refund algorithm (session management, ...)
        ctx = dict(self.env.context, do_not_check_negative_qty=True)
        res = super(PosOrder, self.with_context(ctx)).refund()
        new_order = self.browse(res['res_id'])
        new_order.returned_order_id = self
        new_order.order_type = 'refund'
        new_order.sale_journal = new_order.session_id.config_id.invoice_journal_id

        return res
        
    def action_credit_invoice(self):
        #Nota de Crédito
        journal = self.env['account.journal'].search([('code','=','NCRD')])
        payment_context = {
            "active_ids": self.id, 
            "active_id": self.id
        }
        payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': self.amount_total,
            'journal_id':journal.id,
            'epayment_pos':journal.epayment_id.id,
        })

        payment.with_context(**payment_context).check()

        self.action_pos_order_invoice()
        self.invoice_id.origin = self.returned_order_id.invoice_id.move_id.name
        self.invoice_id.type = 'out_refund'
        self.returned_order_id.returned = True
        self.partner_id.compute_refund_credit()

    @api.multi
    def add_payment(self,data):
        super(PosOrder, self).add_payment(data)
        for order in self:
            for statement_id in order.statement_ids:
                if statement_id.journal_id.code == 'NCRD' and order.order_type == 'sale':
                    order.partner_id.compute_refund_credit()
                    if order.partner_id.refund_credit <= 0:
                        self._logger.info('El Cliente no tiene crédito')
                        # mess= {
                        #     'title':_('Sin crédito!'),
                        #     'message':_('El Cliente no tiene crédito')
                        # }
                        # return {'warning': mess}
                    else:
                        order.partner_id.compute_refund_credit()
                        print(order.partner_id.refund_credit)
