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

    @api.model
    def create_from_ui(self, orders):
        # Keep only new orders
        submitted_references = [o['data']['name'] for o in orders]
        pos_order = self.search([('pos_reference', 'in', submitted_references)])
        existing_orders = pos_order.read(['pos_reference'])
        existing_references = set([o['pos_reference'] for o in existing_orders])
        orders_to_save = [o for o in orders if o['data']['name'] not in existing_references]
        order_ids = []

        for tmp_order in orders_to_save:
            order = tmp_order['data']
            self._match_payment_to_invoice(order)
            pos_order = self._process_order(order)
            order_ids.append(pos_order.id)

            try:
                pos_order.action_pos_order_paid()
            except psycopg2.OperationalError:
                # do not hide transactional errors, the order(s) won't be saved!
                raise
            except Exception as e:
                _logger.error('Could not fully process the POS Order: %s', tools.ustr(e))
            
            pos_order.action_pos_order_invoice()

            return order_ids

    @api.multi
    def action_pos_order_invoice(self):
        super(PosOrder, self).action_pos_order_invoice()
        for order in self:
            if order.order_type  == 'refund':
                order.invoice_id.auth_inv_id = order.sale_journal.auth_out_refund_id
                order.invoice_id.reference = order.sale_journal.auth_out_refund_id.sequence_id.number_next_actual
                for product in order.invoice_id.invoice_line_ids:
                    if product.product_id.property_account_product_refund_id:
                        product.account_id = product.product_id.property_account_product_refund_id
                    elif product.product_id.categ_id.property_account_refund_categ_id:
                        product.account_id = product.product_id.categ_id.property_account_refund_categ_id
            else:
                order.invoice_id.auth_inv_id = order.sale_journal.auth_out_invoice_id
                order.invoice_id.reference = order.sale_journal.auth_out_invoice_id.sequence_id.number_next_actual
                order.sale_journal.sequence_number_next = order.sale_journal.auth_out_invoice_id.sequence_id.number_next_actual
                
            order.invoice_id.reference = order.invoice_id.reference.zfill(9)
            #order.invoice_id.date_invoice = order.date_order
            order.invoice_id.date_invoice = datetime.now() + timedelta(hours=-5)

            for statement_id in order.statement_ids:
                pos_payment_line = {
                    'journal_id': statement_id.journal_id,
                    'code': statement_id.epayment_pos.code,
                    'epayment_id': statement_id.epayment_pos.id,
                    'payment_amount': statement_id.amount,
                    }

                order.invoice_id.pos_payment_line_ids = [(0,0,pos_payment_line)]

            order.invoice_id.sudo().action_invoice_open()
            order.account_move = order.invoice_id.move_id

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
