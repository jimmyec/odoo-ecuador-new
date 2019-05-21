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

class pos_accesskey(models.Model):
    """docstring for pos_access_key"""

    _name = 'pos.accesskey'

    inv_number = fields.Char( 
        'Número de Factura',
        size=15,
        store=True
    )
    access_key = fields.Char(
        'Clave de Acceso',
        size=49,
        store=True
    )   

    @api.multi
    def set_access_key(self, acc_key, i_number):
        do_search = self.env['pos.order'].search([])
        for reference in do_search:
            print(reference.name)
        sql = ' '.join([
            "INSERT INTO pos_accesskey (access_key,inv_number) VALUES ('%s','%s')" % (acc_key[0],i_number[0])
        ])
        self.env.cr.execute(sql)
        return
        
       
class PosOrder(models.Model):
    _inherit = 'pos.order'

    access_key = fields.Char('Clave de Acceso', size=49,)

    def get_pos_code(self):
        code = self.env['ir.sequence'].search([('code','=','pos.edocuments.code')])
        return str(code.number_next_actual).zfill(8)

    def get_code_increse(self):
        code = self.env['ir.sequence'].next_by_code('pos.edocuments.code')
        return code

    def get_inv_number(self,journal):
        inv_number = self.env['account.journal'].search([('id','in',journal)])
        entidad = inv_number.auth_out_invoice_id.serie_entidad
        emision = inv_number.auth_out_invoice_id.serie_emision
        if self.order_type  == 'refund':
            inv_number = str(inv_number.auth_out_invoice_id.sequence_id.number_next_actual).zfill(9)
        else:
            inv_number = str(inv_number.auth_out_refund_id.sequence_id.number_next_actual).zfill(9)
        inv_number = entidad + emision + inv_number
        return inv_number

    def _eval_mod11(self, modulo):
        if modulo == 11:
            return 0
        elif modulo == 10:
            return 1
        else:
            return modulo

    def compute_mod11(self, dato):
        """
        Calculo mod 11
        return int
        """
        total = 0
        weight = 2

        for item in reversed(dato):
            total += int(item) * weight
            weight += 1
            if weight > 7:
                weight = 2
        mod = 11 - total % 11

        mod = self._eval_mod11(mod)
        return mod

    def get_access_key(self, journal_id, date_invoice):
        auth = self.company_id.partner_id.get_authorisation('out_invoice')
        ld = date_invoice.split('-')
        number = self.get_inv_number([journal_id])
        ld.reverse()
        date = ''.join(ld)
        tcomp = self.invoice_id.auth_inv_id.type_id.code
        ruc = self.company_id.partner_id.identifier
        if self.order_type  == 'refund':
            codigo_numero = self.get_pos_code()
        else:
            codigo_numero = self.get_code_increse()
        tipo_emision = self.company_id.emission_code
        env = self.company_id.env_service
        access_key = ''.join([date, tcomp, ruc] + [env] + [number, codigo_numero, tipo_emision])
        modulo = self.compute_mod11(access_key)
        access_key = ''.join([access_key, str(modulo)])
        return access_key

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
            
            pos_order.sale_journal = pos_order.session_id.config_id.invoice_journal_id
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

            order.access_key = order.get_access_key(order.sale_journal.id,order.invoice_id.date_invoice)
            order.invoice_id.clave_acceso = order.access_key
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


