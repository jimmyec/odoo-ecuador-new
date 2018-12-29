# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from datetime import datetime, timedelta

class AccountEpayment(models.Model):
    _name = 'account.epayment'

    code = fields.Char('Código')
    name = fields.Char('Forma de Pago')
        

class PosConfig(models.Model):
    _inherit = 'pos.config'

    default_partner_id = fields.Many2one('res.partner', 'Default Partner')

class Bankstatementepayment(models.Model):
    """docstring for Bankstatementepayment"""
    _inherit = 'account.bank.statement.line'

    epayment_pos = fields.Many2one('account.epayment', 'Forma de Pago')
        

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.multi
    def action_pos_order_invoice(self):
        super(PosOrder, self).action_pos_order_invoice()
        for order in self:
            order.invoice_id.auth_inv_id = order.sale_journal.auth_out_invoice_id

            order.invoice_id.reference = order.sale_journal.auth_out_invoice_id.sequence_id.number_next_actual
            order.sale_journal.sequence_number_next = order.sale_journal.auth_out_invoice_id.sequence_id.number_next_actual
            order.invoice_id.reference = order.invoice_id.reference.zfill(9)
            order.invoice_id.date_invoice = datetime.now() + timedelta(hours=-5)

            for statement_id in order.statement_ids:
                epayment_line = {
                    'code': statement_id.epayment_pos.code,
                    'name': statement_id.epayment_pos.name,
                    'epayment_amount': statement_id.amount,
                    }

                order.invoice_id.epayment_ids = [(0,0,epayment_line)]

            #order.invoice_id.action_invoice_open()

    @api.multi
    def add_payment(self,data):
        super(PosOrder, self).add_payment(data)
        for order in self:
            for statement_id in order.statement_ids:
                if statement_id.journal_id.type == 'cash':
                    statement_id.epayment_pos = self.env['account.epayment'].search([('code','=','01')], limit=1)
                elif statement_id.journal_id.type == 'bank':
                    statement_id.epayment_pos = self.env['account.epayment'].search([('code','=','19')], limit=1)
                else:
                    statement_id.epayment_pos = self.env['account.epayment'].search([('code','=','20')], limit=1)
