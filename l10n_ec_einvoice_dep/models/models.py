# -*- coding: utf-8 -*-

import os
import time
import logging
import itertools
import base64
import io

from odoo import models, fields, api
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from odoo.exceptions import Warning as UserError
from . import utils
from ..xades.sri import DocumentXML
from ..xades.sri import SriService
from ..xades.xades import Xades
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

class AccountEpayment(models.Model):
    _name = 'account.epayment'

    code = fields.Char('Código')
    name = fields.Char('Forma de Pago')

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
        'Autorización',
        size=37,
        readonly=True
    )
    estado_autorizacion = fields.Char(
        'Estado',
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
    autorizado_sri = fields.Boolean('Autorizado?', readonly=True)
    security_code = fields.Char('Código de Seguridad', size=8, readonly=True)
    emission_code = fields.Char('Tipo de Emisión', size=1, readonly=True)
    epayment_id = fields.Many2one('account.epayment', 'Forma de Pago')
    sent = fields.Boolean('Enviado?')

    def get_auth(self, document):
        partner = document.company_id.partner_id
        if document._name == 'account.invoice':
            return document.auth_inv_id
        elif document._name == 'account.retention':
            return partner.get_authorisation('ret_in_invoice')

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
            'razonSocial': company.name,
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
            numero = getattr(self, 'name')
            numero = numero[6:15]
        ld.reverse()
        fecha = ''.join(ld)
#        tcomp = utils.tipoDocumento[auth.type_id.code]
        ruc = self.company_id.partner_id.identifier
        codigo_numero = self.get_code()
        tipo_emision = self.company_id.emission_code
        access_key = (
            [fecha, '01', ruc],
            [numero, codigo_numero, tipo_emision]
            )
        return access_key

    @api.multi
    def _get_codes(self, name='account.invoice'):
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
    def update_document(self, auth, codes):
        fecha = auth.fechaAutorizacion.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.write({
            'numero_autorizacion': auth.numeroAutorizacion,
            'estado_autorizacion': auth.estado,
            'ambiente': auth.ambiente,
            'fecha_autorizacion': fecha,  # noqa
            'autorizado_sri': True,
            'clave_acceso': codes[0],
            'emission_code': codes[1]
        })

    @api.one
    def add_attachment(self, xml_element, auth):
        buf = StringIO.StringIO()
        buf.write(xml_element.encode('utf-8'))
        document = base64.encodestring(buf.getvalue())
        buf.close()
        attach = self.env['ir.attachment'].create(
            {
                'name': '{0}.xml'.format(self.clave_acceso),
                'datas': document,
                'datas_fname':  '{0}.xml'.format(self.clave_acceso),
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary'
            },
        )
        return attach

    @api.multi
    def send_document(self, attachments=None, tmpl=False):
        self.ensure_one()
        self._logger.info('Enviando documento electronico por correo')
        tmpl = self.env.ref(tmpl)
        tmpl.send_mail(  # noqa
            self.id,
            email_values={'attachment_ids': attachments}
        )
        self.sent = True
        return True

#    def render_document(self, document, access_key, emission_code):
#        pass

class Company(models.Model):

    _inherit = 'res.company'

    electronic_signature = fields.Char(
        'Firma Electrónica',
        size=128,
    )
    password_electronic_signature = fields.Char(
        'Clave Firma Electrónica',
        size=255,
    )
    emission_code = fields.Selection(
        [
            ('1', 'Normal'),
            ('2', 'Indisponibilidad')
        ],
        string='Tipo de Emisión',
        required=True,
        default=1
    )
    env_service = fields.Selection(
        [
            ('1', 'Pruebas'),
            ('2', 'Producción')
        ],
        string='Tipo de Ambiente',
        required=True,
        default=1
    )
    contingency_key_ids = fields.One2many(
        'res.company.contingency.key',
        'company_id',
        'Claves de Contingencia',
        help='Claves de contingencia relacionadas con esta empresa.'
    )

class CompanyContingencyKey(models.Model):

    _name = 'res.company.contingency.key'
    _description = 'Claves de Contingencia'

    @api.model
    def _get_company(self):  # , cr, uid, context):
        if self._context.get('company_id', False):
            return self._context.get('company_id')
        else:
            return self.env.user.company_id.id

    key = fields.Char('Clave', size=37, required=True)
    used = fields.Boolean('Activa', readonly=True)
    company_id = fields.Many2one(
        'res.company',
        'Empresa',
        required=True,
        default=_get_company
    )

    _sql_constraints = [
        (
            'key_unique',
            'unique(key)',
            u'Clave de contingencia asignada debe ser única.'
        )
    ]

class AccountInvoice(models.Model):

    _name = 'account.invoice'
    _inherit = ['account.invoice', 'account.edocument']
    _logger = logging.getLogger('account.edocument')
    TEMPLATES = {
        'out_invoice': 'out_invoice.xml',
        'out_refund': 'out_refund.xml'
    }

    def _info_factura(self, invoice):
        """
        """
        def fix_date(date):
            d = time.strftime('%d/%m/%Y',
                              time.strptime(date, '%Y-%m-%d'))
            return d

        company = invoice.company_id
        partner = invoice.partner_id
        infoFactura = {
            'fechaEmision': fix_date(invoice.date_invoice),
            'dirEstablecimiento': company.street2,
            'obligadoContabilidad': 'NO',
            'tipoIdentificacionComprador': utils.tipoIdentificacion[partner.kind_i],  # noqa
            'razonSocialComprador': partner.name,
            'identificacionComprador': partner.identifier,
            'totalSinImpuestos': '%.2f' % (invoice.amount_untaxed),
            'totalDescuento': '0.00',
            'propina': '0.00',
            'importeTotal': '{:.2f}'.format(invoice.amount_pay),
            'moneda': 'DOLAR',
            'formaPago': invoice.epayment_id.code,
            'valorRetIva': '{:.2f}'.format(invoice.taxed_ret_vatsrv+invoice.taxed_ret_vatb),  # noqa
            'valorRetRenta': '{:.2f}'.format(invoice.amount_tax_ret_ir)
        }
#        if company.company_registry:
#            infoFactura.update({'contribuyenteEspecial':
#                                company.company_registry})
#        else:
#            raise UserError('No ha determinado si es contribuyente especial.')

        totalConImpuestos = []
        for tax in invoice.tax_line_ids:
            if tax.group_id.code in ['vat', 'vat0', 'ice']:
                totalImpuesto = {
                    'codigo': utils.tabla17[tax.group_id.code],
                    'codigoPorcentaje': utils.tabla18[tax.percent_report],
                    'baseImponible': '{:.2f}'.format(tax.base),
                    'tarifa': tax.percent_report,
                    'valor': '{:.2f}'.format(tax.amount)
                    }
                totalConImpuestos.append(totalImpuesto)

        infoFactura.update({'totalConImpuestos': totalConImpuestos})

        compensaciones = False
        comp = self.compute_compensaciones()
        if comp:
            compensaciones = True
            infoFactura.update({
                'compensaciones': compensaciones,
                'comp': comp
            })

        if self.type == 'out_refund':
            inv = self.search([('number', '=', self.origin)], limit=1)
            inv_number = '{0}-{1}-{2}'.format(inv.invoice_number[:3], inv.invoice_number[3:6], inv.invoice_number[6:])  # noqa
            notacredito = {
                'codDocModificado': inv.auth_inv_id.type_id.code,
                'numDocModificado': inv_number,
                'motivo': self.name,
                'fechaEmisionDocSustento': fix_date(inv.date_invoice),
                'valorModificacion': self.amount_total
            }
            infoFactura.update(notacredito)
        return infoFactura

    def _detalles(self, invoice):
        """
        """
        def fix_chars(code):
            special = [
                [u'%', ' '],
                [u'º', ' '],
                [u'Ñ', 'N'],
                [u'ñ', 'n']
            ]
            for f, r in special:
                code = code.replace(f, r)
            return code

        detalles = []
        for line in invoice.invoice_line_ids:
            codigoPrincipal = line.product_id and \
                line.product_id.default_code and \
                fix_chars(line.product_id.default_code) or '001'
            priced = line.price_unit * (1 - (line.discount or 0.00) / 100.0)
            discount = (line.price_unit - priced) * line.quantity
            detalle = {
                'codigoPrincipal': codigoPrincipal,
                'descripcion': fix_chars(line.name.strip()),
                'cantidad': '%.6f' % (line.quantity),
                'precioUnitario': '%.6f' % (line.price_unit),
                'descuento': '%.2f' % discount,
                'precioTotalSinImpuesto': '%.2f' % (line.price_subtotal)
            }
            impuestos = []
            for tax_line in line.invoice_line_tax_ids:
                if tax_line.tax_group_id.code in ['vat', 'vat0', 'ice']:
                    impuesto = {
                        'codigo': utils.tabla17[tax_line.tax_group_id.code],
                        'codigoPorcentaje': utils.tabla18[tax_line.percent_report],  # noqa
                        'tarifa': tax_line.percent_report,
                        'baseImponible': '{:.2f}'.format(line.price_subtotal),
                        'valor': '{:.2f}'.format(line.price_subtotal *
                                                 tax_line.amount / 100)
                    }
                    impuestos.append(impuesto)
            detalle.update({'impuestos': impuestos})
            detalles.append(detalle)
        return {'detalles': detalles}

    def _compute_discount(self, detalles):
        total = sum([float(det['descuento']) for det in detalles['detalles']])
        return {'totalDescuento': total}

    def render_document(self, invoice, access_key, emission_code):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        einvoice_tmpl = env.get_template(self.TEMPLATES[self.type])
        data = {}
        data.update(self._info_tributaria(invoice, access_key, emission_code))
        data.update(self._info_factura(invoice))
        detalles = self._detalles(invoice)
        data.update(detalles)
        data.update(self._compute_discount(detalles))
        einvoice = einvoice_tmpl.render(data)
        return einvoice

    def render_authorized_einvoice(self, autorizacion):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        einvoice_tmpl = env.get_template('authorized_einvoice.xml')
        auth_xml = {
            'estado': autorizacion.estado,
            'numeroAutorizacion': autorizacion.numeroAutorizacion,
            'ambiente': autorizacion.ambiente,
            'fechaAutorizacion': str(autorizacion.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),  # noqa
            'comprobante': autorizacion.comprobante
        }
        auth_invoice = einvoice_tmpl.render(auth_xml)
        return auth_invoice

    @api.multi
    def action_generate_einvoice(self):
        """
        Metodo de generacion de factura electronica
        TODO: usar celery para enviar a cola de tareas
        la generacion de la factura y envio de email
        """
        for obj in self:
            if obj.type not in ['out_invoice', 'out_refund']:
                continue
            self.check_date(obj.date_invoice)
            self.check_before_sent()
            access_key, emission_code = self._get_codes(name='account.invoice')
            einvoice = self.render_document(obj, access_key, emission_code)
            inv_xml = DocumentXML(einvoice, obj.type)
            inv_xml.validate_xml()
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(einvoice, file_pk12, password)

            message="""
            %s <br>
            """ % (einvoice)
            self.message_post(body=signed_document)

#            ok, errores = inv_xml.send_receipt(signed_document)
#            if not ok:
#                raise UserError(errores)
#            auth, m = inv_xml.request_authorization(access_key)
#            if not auth:
#                msg = ' '.join(list(itertools.chain(*m)))
#                raise UserError(msg)
#            auth_einvoice = self.render_authorized_einvoice(auth)
#            self.update_document(auth, [access_key, emission_code])
#            attach = self.add_attachment(auth_einvoice, auth)
#            message = """
#            DOCUMENTO ELECTRONICO GENERADO <br>
#            CLAVE DE ACCESO: %s <br>
#            NUMERO DE AUTORIZACION %s <br>
#            FECHA AUTORIZACION: %s <br>
#            ESTADO DE AUTORIZACION: %s <br>
#            AMBIENTE: %s <br>
#            """ % (
#                self.clave_acceso,
#                self.numero_autorizacion,
#                self.fecha_autorizacion,
#                self.estado_autorizacion,
#                self.ambiente
#            )
#            self.message_post(body=message)
#            self.send_document(
#                attachments=[a.id for a in attach],
#                tmpl='l10n_ec_einvoice_dep.email_template_einvoice'
#            )

    @api.multi
    def invoice_print(self):
        return self.env['report'].get_action(
            self,
            'l10n_ec_einvoice_dep.report_einvoice'
        )

class AccountWithdrawing(models.Model):

    _name = 'account.retention'
    _inherit = ['account.retention', 'account.edocument']
    _logger = logging.getLogger(_name)

    def get_secuencial(self):
        return getattr(self, 'name')[6:15]

    def _info_withdrawing(self, withdrawing):
        """
        """
        # generar infoTributaria
        company = withdrawing.company_id
        partner = withdrawing.invoice_id.partner_id
        infoCompRetencion = {
            'fechaEmision': time.strftime('%d/%m/%Y', time.strptime(withdrawing.date, '%Y-%m-%d')),  # noqa
            'dirEstablecimiento': company.street,
            'obligadoContabilidad': 'SI',
            'tipoIdentificacionSujetoRetenido': utils.tipoIdentificacion[partner.type_ced_ruc],  # noqa
            'razonSocialSujetoRetenido': partner.name,
            'identificacionSujetoRetenido': partner.ced_ruc,
            'periodoFiscal': withdrawing.period_id.name,
            }
        if company.company_registry:
            infoCompRetencion.update({'contribuyenteEspecial': company.company_registry})  # noqa
        return infoCompRetencion

    def _impuestos(self, retention):
        """
        """
        def get_codigo_retencion(linea):
            if linea.tax_group in ['ret_vat_b', 'ret_vat_srv']:
                return utils.tabla21[line.percent]
            else:
                code = linea.base_code_id and linea.base_code_id.code or linea.tax_code_id.code  # noqa
                return code

        impuestos = []
        for line in retention.tax_ids:
            impuesto = {
                'codigo': utils.tabla20[line.tax_group],
                'codigoRetencion': get_codigo_retencion(line),
                'baseImponible': '%.2f' % (line.base),
                'porcentajeRetener': str(line.percent),
                'valorRetenido': '%.2f' % (abs(line.amount)),
                'codDocSustento': retention.invoice_id.sustento_id.code,
                'numDocSustento': line.num_document,
                'fechaEmisionDocSustento': time.strftime('%d/%m/%Y', time.strptime(retention.invoice_id.date_invoice, '%Y-%m-%d'))  # noqa
            }
            impuestos.append(impuesto)
        return {'impuestos': impuestos}

    def render_document(self, document, access_key, emission_code):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        ewithdrawing_tmpl = env.get_template('ewithdrawing.xml')
        data = {}
        data.update(self._info_tributaria(document, access_key, emission_code))
        data.update(self._info_withdrawing(document))
        data.update(self._impuestos(document))
        edocument = ewithdrawing_tmpl.render(data)
        self._logger.debug(edocument)
        return edocument

    def render_authorized_document(self, autorizacion):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        edocument_tmpl = env.get_template('authorized_withdrawing.xml')
        auth_xml = {
            'estado': autorizacion.estado,
            'numeroAutorizacion': autorizacion.numeroAutorizacion,
            'ambiente': autorizacion.ambiente,
            'fechaAutorizacion': str(autorizacion.fechaAutorizacion.strftime("%d/%m/%Y %H:%M:%S")),  # noqa
            'comprobante': autorizacion.comprobante
        }
        auth_withdrawing = edocument_tmpl.render(auth_xml)
        return auth_withdrawing

    @api.multi
    def action_generate_document(self):
        """
        """
        for obj in self:
            self.check_date(obj.date)
            self.check_before_sent()
            access_key, emission_code = self._get_codes('account.retention')
            ewithdrawing = self.render_document(obj, access_key, emission_code)
            self._logger.debug(ewithdrawing)
            inv_xml = DocumentXML(ewithdrawing, 'withdrawing')
            inv_xml.validate_xml()
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(ewithdrawing, file_pk12, password)
            ok, errores = inv_xml.send_receipt(signed_document)
            if not ok:
                raise UserError(errores)
            auth, m = inv_xml.request_authorization(access_key)
            if not auth:
                msg = ' '.join(list(itertools.chain(*m)))
                raise UserError(msg)
            auth_document = self.render_authorized_document(auth)
            self.update_document(auth, [access_key, emission_code])
            attach = self.add_attachment(auth_document, auth)
            self.send_document(
                attachments=[a.id for a in attach],
                tmpl='l10n_ec_einvoice.email_template_eretention'
            )
            return True

    @api.multi
    def retention_print(self):
        return self.env['report'].get_action(
            self,
            'l10n_ec_einvoice_dep.report_eretention'
        )

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_generate_eretention(self):
        for obj in self:
            if not obj.journal_id.auth_ret_id.is_electronic:
                return True
            obj.retention_id.action_generate_document()

    @api.multi
    def action_retention_create(self):
        super(AccountInvoice, self).action_retention_create()
        for obj in self:
            if obj.type in ['in_invoice', 'liq_purchase']:
                self.action_generate_eretention()
