# -*- coding: utf-8 -*-

import os
import io
import time
import logging
import itertools

from odoo import models, fields, api

from jinja2 import Environment, FileSystemLoader
from openerp.exceptions import Warning as UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from . import utils
from ..xades.sri import DocumentXML
from ..xades.xades import Xades

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
            'obligadoContabilidad': company.forced_account,
            'tipoIdentificacionComprador': utils.tipoIdentificacion[partner.type_id],  # noqa
            'razonSocialComprador': partner.name,
            'identificacionComprador': partner.identifier,
            'totalSinImpuestos': '%.2f' % (invoice.amount_untaxed),
            'totalDescuento': '0.00',
            'propina': '0.00',
            'importeTotal': '{:.2f}'.format(invoice.amount_pay),
            'moneda': 'DOLAR',
            #'formaPago': invoice.epayment_ids.code,
            'valorRetIva': '{:.2f}'.format(invoice.taxed_ret_vatsrv+invoice.taxed_ret_vatb),  # noqa
            'valorRetRenta': '{:.2f}'.format(invoice.amount_tax_ret_ir)
        }
        if company.company_registry:
            infoFactura.update({'contribuyenteEspecial':
                                company.company_registry})
        else:
            raise UserError('No ha determinado si es contribuyente especial.')

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
        else:
            formaPago = []
            if self.pos_payment_line_ids:
                for pos_payment_id in self.pos_payment_line_ids:
                    pago = {
                        'codigo': pos_payment_id.code,
                        'monto': pos_payment_id.payment_amount, 
                    }
                    formaPago.append(pago)
                    self.payment_term = pos_payment_id.epayment_id.name
                
                infoFactura.update({'formaPago': formaPago})
            elif self.payment_ids:
                for payment_id in self.payment_ids:
                    pago = {
                        'codigo': payment_id.journal_id.epayment_id.code,
                        'monto': payment_id.amount, 
                    }
                    formaPago.append(pago)
                    self.payment_term = payment_id.journal_id.epayment_id.name
                
                infoFactura.update({'formaPago': formaPago})
            else:
                plazo = 0
                if invoice.payment_term_id:
                    for terms in invoice.payment_term_id.line_ids:
                        plazo += terms.days
                else:
                    raise UserError('Ingresar Pago o Plazos de pago')
                
                pago = {
                    'codigo': '20',
                    'monto': '{:.2f}'.format(invoice.amount_pay),
                    'plazo': str(plazo),
                    'unidadTiem': 'dias',
                }

                formaPago.append(pago)
                infoFactura.update({'formaPago': formaPago})
                self.payment_term = 'OTROS CON UTILIZACION DEL SISTEMA FINANCIERO'
                #raise UserError('Ingresar Pago')

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
                'cantidad': '%.2f' % (line.quantity),
                'precioUnitario': '%.2f' % (line.price_unit),
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
        return {'totalDescuento': '{:.2f}'.format(total)}

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
            
            aux_acces_key = str(self.clave_acceso)
            emission_code = obj.company_id.emission_code
            if self.estado_factura == 'process':
                access_key = self.clave_acceso
            elif self.clave_acceso:
                self.SriServiceObj.set_active_env(self.env.user.company_id.env_service)
                access_key = self.clave_acceso
            else:
                access_key, emission_code = self._get_codes(name='account.invoice')
            einvoice = self.render_document(obj, access_key, emission_code)
            self._logger.info(einvoice)
            inv_xml = DocumentXML(einvoice, obj.type)
            if not inv_xml.validate_xml():
                self.write({'estado_factura': 'invalid'})
                return
                #raise UserError('Documento no valido')
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(einvoice, file_pk12, password)
            self.update_document([access_key, emission_code])
            if self.estado_factura != 'process':
                ok, errores = inv_xml.send_receipt(signed_document)
                if not ok:
                    self._logger.info(errores)
                    self.write({'estado_factura': 'send_error'})
                    if errores == 'ERROR CLAVE ACCESO REGISTRADA ' or errores == 'ERROR ERROR SECUENCIAL REGISTRADO ':

                        self.write({
                            'autorizado_sri': True,
                            'to_send_einvoice': True,
                            'estado_correo': 'to_send',
                            'estado_autorizacion': 'Autorizado',
                            'ambiente': 'PRODUCCION',
                            #'fecha_autorizacion': fecha,  # noqa
                            'estado_factura': 'is_auth',
                        })
                        
                        message = """
                        DOCUMENTO ELECTRONICO GENERADO <br><br>
                        CLAVE DE ACCESO / NUMERO DE AUTORIZACION: %s <br>
                        ESTADO: AUTORIZADO <br>
                        FECHA DE AUTORIZACIÓN:  <br>
                        AMBIENTE: PRODUCCION <br>
                        """ % (
                            aux_acces_key,
                        )
                        
                        self.message_post(body=message)
                        self.clave_acceso = aux_acces_key
                        xml_attach = self.add_attachment(einvoice.encode(),aux_acces_key)
                        self.store_fname = xml_attach[0].datas_fname
                        self.xml_file = xml_attach[0].datas
                        
                    return
                    #raise UserError(errores)

            auth, m = inv_xml.request_authorization(access_key)
            if not auth:
                msg = ' '.join(list(itertools.chain(*m)))
                self._logger.info(msg)
                self.write({'estado_factura': 'no_auth'})
                return
                #raise UserError(msg)
            if auth.estado == 'EN PROCESO':
                self.write({'estado_factura': 'process'})
                return

            fecha = auth.fechaAutorizacion.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            self.write({
                'autorizado_sri': True,
                'to_send_einvoice': True,
                'estado_correo': 'to_send',
                'estado_autorizacion': auth.estado,
                'ambiente': auth.ambiente,
                'fecha_autorizacion': fecha,  # noqa
                'estado_factura': 'is_auth',
            })
            
            message = """
            DOCUMENTO ELECTRONICO GENERADO <br><br>
            CLAVE DE ACCESO / NUMERO DE AUTORIZACION: %s <br>
            ESTADO: %s <br>
            FECHA DE AUTORIZACIÓN: %s <br>
            AMBIENTE: %s <br>
            """ % (
                access_key,
                auth.estado,
                fecha,
                auth.ambiente,
            )
            self.message_post(body=message)
            auth_einvoice = self.render_authorized_einvoice(auth)
            xml_attach = self.add_attachment(auth_einvoice.encode(),self.clave_acceso)
            self.store_fname = xml_attach[0].datas_fname
            self.xml_file = xml_attach[0].datas
            #self.action_send_einvoice_email()auth, m = inv_xml.request_authorization(access_key)

    @api.multi
    def action_send_einvoice_email(self):
        for obj in self:
            if obj.type not in ['out_invoice', 'out_refund']:
                continue
            inv_name = str(self.clave_acceso) + '.xml'
            attach = self.env['ir.attachment'].search([('name','=',inv_name)])
            #attach = attach_ids[0]
            pdf = self.env.ref('l10n_ec_einvoice.report_einvoice').render_qweb_pdf(self.ids)
            pdf_name = str(self.clave_acceso) + '.pdf'
            attach_pdf = self.env['ir.attachment'].search([('name','=',pdf_name)])#self.add_attachment_pdf(pdf,self.clave_acceso)
            self.send_document(
                attachments=[a.id for a in attach[0] + attach_pdf[0]],
                tmpl='l10n_ec_einvoice.email_template_einvoice'
            )
            self.write({
                'to_send_einvoice': False,
                'estado_correo': 'sent'
            })
            message = """
            El correo electrónico al cliente ha sido enviado correctamente<br><br>
            """ 
            if not self.to_send_einvoice:
                self.message_post(body=message)

    @api.multi
    def invoice_print(self):
        return self.env.ref('l10n_ec_einvoice.report_einvoice').report_action(self)

    payment_move_line_ids = fields.Many2many(
        'account.move.line', 
        string='Payment Move Lines',
        readonly = True,
        store = True,
        )
            