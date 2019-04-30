# -*- coding: utf-8 -*-

import os
import time
import logging
import itertools

from jinja2 import Environment, FileSystemLoader

from openerp import models, api
from openerp.exceptions import Warning as UserError

from . import utils
from ..xades.sri import DocumentXML
from ..xades.xades import Xades


class AccountWithdrawing(models.Model):

    _name = 'account.retention'
    _inherit = ['account.retention', 'account.edocument']
    _logger = logging.getLogger(_name)

    def get_secuencial(self):
        return getattr(self, 'name')[6:]

    def _info_withdrawing(self, withdrawing):
        """
        """
        # generar infoTributaria
        company = withdrawing.company_id
        partner = withdrawing.invoice_id.partner_id
        for tax_id in withdrawing.tax_ids:
            fiscal_period = tax_id.fiscal_period
        infoCompRetencion = {
            'fechaEmision': time.strftime('%d/%m/%Y', time.strptime(withdrawing.date, '%Y-%m-%d')),  # noqa
            'dirEstablecimiento': company.street,
            'obligadoContabilidad': 'SI',
            'tipoIdentificacionSujetoRetenido': utils.tipoIdentificacion[partner.type_id],  # noqa
            'razonSocialSujetoRetenido': partner.name,
            'identificacionSujetoRetenido': partner.identifier,
            'periodoFiscal': fiscal_period,
            }
        if company.company_registry:
            infoCompRetencion.update({'contribuyenteEspecial': company.company_registry})  # noqa
        return infoCompRetencion

    def _impuestos(self, retention):
        """
        """
        def get_codigo_retencion(linea):
            if linea.group_id.code in ['ret_vat_b', 'ret_vat_srv']:
                return utils.tabla21[str(line.tax_id.percent_report)]
            else:
                code = linea.tax_id and linea.tax_id.description or linea.tax_code_id.code  # noqa
                return code

        def get_line_base(linea):
            if linea.group_id.code in ['ret_vat_b', 'ret_vat_srv']:
                return '%.2f' % (linea.base*0.12)
            else:
                return '%.2f' % (linea.base)

        impuestos = []
        for line in retention.tax_ids:
            impuesto = {
                'codigo': utils.tabla20[line.group_id.code],
                'codigoRetencion': get_codigo_retencion(line),
                'baseImponible': get_line_base(line),
                'porcentajeRetener': str(line.tax_id.percent_report),
                'valorRetenido': '%.2f' % (abs(line.amount)),
                'codDocSustento': retention.invoice_id.sustento_id.code,
                'numDocSustento': retention.invoice_id.invoice_number,
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
        data.update({'secuencial': self.name})
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
            access_key, emission_code = self._get_codes(name='account.retention')
            ewithdrawing = self.render_document(obj, access_key, emission_code)
            inv_xml = DocumentXML(ewithdrawing, 'withdrawing')
            #if not inv_xml.validate_xml():
            #    raise UserError('Documento no valido')
            xades = Xades()
            file_pk12 = obj.company_id.electronic_signature
            password = obj.company_id.password_electronic_signature
            signed_document = xades.sign(ewithdrawing, file_pk12, password)
            self._logger.info(signed_document)
            ok, errores = inv_xml.send_receipt(signed_document)
            if not ok:
                raise UserError(errores)
            auth, m = inv_xml.request_authorization(access_key)
            if not auth:
                msg = ' '.join(list(itertools.chain(*m)))
                raise UserError(msg)
            auth_eretention = self.render_authorized_document(auth)
            self.update_document([access_key, emission_code])
            xml_attach = self.add_attachment(auth_eretention.encode(),self.clave_acceso)
            self.store_fname = xml_attach[0].datas_fname
            self.xml_file = xml_attach[0].datas
            #self.add_attachment(auth_eretention.encode(),self.name)
            self.action_send_eretention_email()
            return True

    @api.multi
    def action_send_eretention_email(self):
        for obj in self:
            ret_name = str(self.clave_acceso + '.xml')
            attach = self.env['ir.attachment'].search([('name','=',ret_name)])
            #attach = attach_ids[0]
            pdf = self.env.ref('l10n_ec_einvoice.report_eretention').render_qweb_pdf(self.ids)
            attach_pdf = self.add_attachment_pdf(pdf,self.name)
            attachments=[a.id for a in attach[0] + attach_pdf[0]]
            self.ensure_one()
            self._logger.info('Enviando documento electronico por correo')
            template = self.env.ref('l10n_ec_einvoice.email_template_einvoice')
            self.env['mail.template'].browse(template.id).send_mail(self.id, email_values={'attachment_ids': attachments}, force_send=True, raise_exception=True)
            self._logger.info('Documento enviado')
            self.sent = True
            # self.send_document(
            #     attachments=[a.id for a in attach + attach_pdf],
            #     tmpl='l10n_ec_einvoice.email_template_eretention'
            # )

    @api.multi
    def retention_print(self):
        return self.env.ref('l10n_ec_einvoice.report_eretention').report_action(self)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_generate_eretention(self):
        for obj in self:
            if not obj.journal_id.auth_retention_id.is_electronic:
                return True
            obj.retention_id.action_generate_document()

    @api.multi
    def action_retention_create(self):
        #super(AccountInvoice, self).action_withholding_create()
        for obj in self:
            if obj.type in ['in_invoice', 'liq_purchase']:
                self.action_generate_eretention()
