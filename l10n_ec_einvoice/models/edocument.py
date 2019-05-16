# -*- coding: utf-8 -*-

import base64
import io
from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import Warning as UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from . import utils
from ..xades.sri import SriService


class AccountEpayment(models.Model):
    _name = 'account.pos.payment'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[('type','in',['bank','cash'])],
        )
    code = fields.Char(
        string='Código',
        readonly = True,
        )
    epayment_id = fields.Many2one(
        'account.epayment',
        string='Forma de Pago',
        readonly = True,
        )
    payment_amount = fields.Char(
        string='Monto',
        store=True
        )

class AccountPayment(models.Model):
    _inherit = 'account.journal'

    epayment_id = fields.Many2one(
        'account.epayment',
        string='Forma de Pago',
        )


class Edocument(models.AbstractModel):

    _name = 'account.edocument'
    _FIELDS = {
        'account.invoice': 'invoice_number',
        'account.retention': 'name'
    }
    SriServiceObj = SriService()

    clave_acceso = fields.Char(
        'Clave de Acceso',
        size=49,
        readonly=True
    )
    numero_autorizacion = fields.Char(
        'Número de Autorización',
        size=37,
        readonly=True
    )
    estado_autorizacion = fields.Char(
        'Estado de Autorización',
        size=64,
        readonly=True
    )
    fecha_autorizacion = fields.Datetime(
        'Fecha Autorización',
        readonly=True
    )
    ambiente = fields.Char(
        'Ambiente',
        size=64,
        readonly=True
    )
    estado_factura = fields.Selection(
        [('invalid', 'Documento no válido'),
         ('send_error', 'Error al enviar'),
         ('no_auth', 'No Autorizado'),
         ('process', 'En Proceso'),
         ('is_auth', 'Autorizado')],
        string='Estado',
        readonly=True,
    )
    estado_correo = fields.Selection(
        [('no_send', 'No enviar'),
         ('to_send', 'Enviar'),
         ('sent', 'Enviado')],
        string='Correo',
        readonly=True,
    )
    autorizado_sri = fields.Boolean('Autorizado SRI',readonly=True)
    is_credit = fields.Boolean('Crédito',readonly=True)
    is_credit_payment = fields.Boolean('Crédito',readonly=True)
    to_send_einvoice = fields.Boolean('Enviar email',readonly=True)
    security_code = fields.Char('Código de Seguridad', size=8, readonly=True)
    emission_code = fields.Char('Tipo de Emisión', size=1, readonly=True)
    pos_payment_line_ids = fields.Many2many('account.pos.payment','epayment_id',string='Forma de Pago')
    epayment_id = fields.Many2one('account.epayment', default=lambda self:self.env['account.epayment'].search([('code','=','01')]))
    sent = fields.Boolean('Enviado?')
    payment_term = fields.Char()
    xml_file = fields.Binary('XML')
    store_fname = fields.Char(string="Factura")

    def get_auth(self, document):
        partner = document.company_id.partner_id
        if document._name == 'account.invoice':
            return document.auth_inv_id
        elif document._name == 'account.retention':
            return document.auth_inv_id#partner.get_authorisation('ret_in_invoice')

    def get_secuencial(self):
        return getattr(self, self._FIELDS[self._name])[6:]

    def _info_tributaria(self, document, access_key, emission_code):
        """
        """
        company = document.company_id
        auth = self.get_auth(document)
        infoTributaria = {
            'ambiente': self.env.user.company_id.env_service,
            'tipoEmision': emission_code,
            'razonSocial': company.namerl,
            'nombreComercial': company.name,
            'ruc': company.partner_id.identifier,
            'claveAcceso':  access_key,
            'codDoc': utils.tipoDocumento[auth.type_id.code],
            'estab': auth.serie_entidad,
            'ptoEmi': auth.serie_emision,
            'secuencial': self.get_secuencial(),
            'dirMatriz': company.street
        }
        return infoTributaria

    def get_code(self):
        code = self.env['ir.sequence'].next_by_code('edocuments.code')
        return code

    def get_access_key(self, name):
        if name == 'account.invoice':
            auth = self.company_id.partner_id.get_authorisation('out_invoice')
            ld = self.date_invoice.split('-')
            numero = getattr(self, 'invoice_number')
        elif name == 'account.retention':
            auth = self.company_id.partner_id.get_authorisation('ret_in_invoice')  # noqa
            ld = self.date.split('-')
            numero = getattr(self, 'withholding_number')
            #numero = numero[6:15]
        ld.reverse()
        fecha = ''.join(ld)
        tcomp = self.auth_inv_id.type_id.code
        ruc = self.company_id.partner_id.identifier
        codigo_numero = self.get_code()
        tipo_emision = self.company_id.emission_code
        access_key = (
            [fecha, tcomp, ruc],
            [numero, codigo_numero, tipo_emision]
            )
        return access_key

    @api.multi
    def _get_codes(self, name):
        ak_temp = self.get_access_key(name)
        self.SriServiceObj.set_active_env(self.env.user.company_id.env_service)
        access_key = self.SriServiceObj.create_access_key(ak_temp)
        emission_code = self.company_id.emission_code
        return access_key, emission_code

    @api.multi
    def check_before_sent(self):
        """
        """
        MESSAGE_SEQUENCIAL = ' '.join([
            u'Los comprobantes electrónicos deberán ser',
            u'enviados al SRI para su autorización en orden cronológico',
            'y secuencial. Por favor enviar primero el',
            ' comprobante inmediatamente anterior.'])
        FIELD = {
            'account.invoice': 'invoice_number',
            'account.retention': 'name'
        }
        number = getattr(self, FIELD[self._name])
        sql = ' '.join([
            "SELECT autorizado_sri, %s FROM %s" % (FIELD[self._name], self._table),  # noqa
            "WHERE state='open' AND %s < '%s'" % (FIELD[self._name], number),  # noqa
            self._name == 'account.invoice' and "AND type = 'out_invoice'" or '',  # noqa
            "ORDER BY %s DESC LIMIT 1" % FIELD[self._name]
        ])
        self.env.cr.execute(sql)
        res = self.env.cr.fetchone()
        if not res:
            return True
        auth, number = res
        if auth is None and number:
            raise UserError(MESSAGE_SEQUENCIAL)
        return True

    def check_date(self, date_invoice):
        """
        Validar que el envío del comprobante electrónico
        se realice dentro de las 24 horas posteriores a su emisión
        """
        LIMIT_TO_SEND = 5
        MESSAGE_TIME_LIMIT = u' '.join([
            u'Los comprobantes electrónicos deben',
            u'enviarse con máximo 24h desde su emisión.']
        )
        dt = datetime.strptime(date_invoice, '%Y-%m-%d')
        days = (datetime.now() - dt).days
        if days > LIMIT_TO_SEND:
            raise UserError(MESSAGE_TIME_LIMIT)

    @api.multi
    def update_document(self, codes):
        self.write({
            'numero_autorizacion': codes[0],
            'clave_acceso': codes[0],
            'emission_code': codes[1]
        })

    @api.one
    def add_attachment(self, xml_element, xml_name):
        buf = io.BytesIO()
        buf.write(xml_element)
        document = base64.encodestring(buf.getvalue())
        buf.close()
        file_name = str(xml_name) + '.xml'
        attach = self.env['ir.attachment'].create(
            {
                'name': file_name.format(self.clave_acceso),
                'datas': document,
                'datas_fname':  file_name.format(self.clave_acceso),
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary',
            },
        )
        return attach

    @api.one
    def add_attachment_pdf(self, pdf_file, pdf_name):
        b64_pdf = base64.b64encode(pdf_file[0])
        file_name = str(pdf_name) + '.pdf'
        attach = self.env['ir.attachment'].create(
            {
                'name': file_name.format(self.clave_acceso),
                'type': 'binary',
                'datas': b64_pdf,
                'datas_fname':  file_name.format(self.clave_acceso),
                'store_fname': 'ride',
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/x-pdf'
            },
        )
        return attach

    @api.multi
    def send_document(self, attachments, tmpl):
        self.ensure_one()
        self._logger.info('Enviando documento electronico por correo')

        template = False
        template = self.env.ref(tmpl)
        self.env['mail.template'].browse(template.id).send_mail(self.id, email_values={'attachment_ids': attachments}, force_send=True, raise_exception=True)
        self._logger.info('Documento enviado')
        self.sent = True
        return True

    def render_document(self, document, access_key, emission_code):
        pass
