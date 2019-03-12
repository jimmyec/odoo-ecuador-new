# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.exceptions import Warning as UserError
        
class RefundInvoice(models.Model):
    """docstring for ClassName"""
    _inherit = 'account.invoice'

    is_credit = fields.Boolean(
        string='Credito',
        default=False,
        readonly=True,
    )

    is_credit_payment = fields.Boolean(
        string='Pagado con crédito',
        default=False,
        readonly=True,
    )

class PosRefundCredit(models.Model):
    _inherit = 'res.partner'

    @api.one
    def compute_refund_credit(self):
        """
        Metodo ...
        """
        refund_invoices = self.env['account.invoice'].search([('partner_id.id','=',self.id),('type','=','out_refund'),('is_credit','=',True)])
        
        for refund_invoice in refund_invoices:
            self.refund_credit += refund_invoice.amount_total

    refund_credit = fields.Monetary(
        string='Credito',
        compute='compute_refund_credit',
        store=True,
        help='Crédito en Devoluciones o Notas de Crédito',
    )
   # property_account_refund_id = fields.Many2one(
   #     comodel_name='account.account',
   #     string='Cuenta de devoluciones',
   #     required=False,
   # )

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

    def refund(self):
        # Call super to use original refund algorithm (session management, ...)
        ctx = dict(self.env.context, do_not_check_negative_qty=True)
        res = super(PosOrder, self.with_context(ctx)).refund()
        new_order = self.browse(res['res_id'])
        new_order.returned_order_id = self
        new_order.order_type = 'refund'

        return res
        
    def action_credit_invoice(self):
        #Nota de Crédito
        payment_context = {"active_ids": self.id, "active_id": self.id}
        payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': self.amount_total,
            #'journal_id': self.env['account.journal'].search([('code','=','NCRD')], limit=1)
        })

        payment.with_context(**payment_context).check()

        self.action_pos_order_invoice()
        self.invoice_id.is_credit = True
        self.invoice_id.origin = self.returned_order_id.invoice_id.move_id.name
        #self.invoice_id.account_id = self.partner_id.property_account_refund_id
        self.invoice_id.type = 'out_refund'
        for product in self.invoice_id.invoice_line_ids:
            if product.product_id.property_account_product_refund_id:
                product.account_id = product.product_id.property_account_product_refund_id
            elif product.product_id.categ_id.property_account_refund_categ_id:
                product.account_id = product.product_id.categ_id.property_account_refund_categ_id

        self.partner_id.compute_refund_credit()
        #self.invoice_id.sudo().action_invoice_open()

    @api.multi
    def add_payment(self,data):
        super(PosOrder, self).add_payment(data)
        for order in self:
            for statement_id in order.statement_ids:
                if statement_id.journal_id.code == 'NCRD' and order.order_type == 'sale':
                    if order.partner_id.refund_credit <= 0:
                        self._logger.info('El Cliente no tiene crédito')
                        #raise UserError('El Cliente no tiene crédito')
                    else:
                        refund_invoices = self.env['account.invoice'].search([('partner_id.id','=',self.partner_id.id),('type','=','out_refund'),('is_credit','=',True)])
                        for refund_invoice in refund_invoices:
                            refund_invoice.is_credit = False
                        order.partner_id.compute_refund_credit()
                        print(order.partner_id.refund_credit)
