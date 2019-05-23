# -*- coding: utf-8 -*-

import base64
import io
import os
import logging
from itertools import groupby
from operator import itemgetter

from lxml import etree
from lxml.etree import DocumentInvalid
from jinja2 import Environment, FileSystemLoader
from odoo.exceptions import Warning as UserError

from odoo import models, fields, api

from .utils import convertir_fecha, get_date_value

tpIdProv = {
    'ruc': '01',
    'cedula': '02',
    'pasaporte': '03',
}

tpIdCliente = {
    'ruc': '04',
    'cedula': '05',
    'pasaporte': '06'
    }


class AccountAts(dict):
    """
    representacion del ATS
    >>> ats.campo = 'valor'
    >>> ats['campo']
    'valor'
    """

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, item, value):
        if item in self.__dict__:
            dict.__setattr__(self, item, value)
        else:
            self.__setitem__(item, value)


class WizardAts(models.TransientModel):
    _name = 'wizard.ats'
    _description = 'Anexo Transaccional Simplificado'
    _logger = logging.getLogger(_name)

    @api.multi
    def _get_period(self):
        result = {}
        for obj in self:
            result[obj.id] = self.env['account.period'].find(obj.date)[0]
        return result

    @api.multi
    def _get_company(self):
        return self.env.user.company_id.id

    def act_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    def process_lines(self, lines, baseImponible):
        """
        @temp: {'332': {baseImpAir: 0,}}
        @data_air: [{baseImpAir: 0, ...}]
        """
        data_air = []
        temp = {}
        for line in lines:
            if line.group_id.code in ['ret_ir', 'no_ret_ir']:
                if not temp.get(line.tax_id.description):
                    temp[line.tax_id.description] = {
                        'baseImpAir': 0,
                        'valRetAir': 0
                    }
                temp[line.tax_id.description]['baseImpAir'] += line.base
                temp[line.tax_id.description]['baseImpAir'] = '%.2f' % temp[line.tax_id.description]['baseImpAir']
                temp[line.tax_id.description]['codRetAir'] = line.tax_id.description  # noqa
                temp[line.tax_id.description]['porcentajeAir'] = '%.2f' % abs(int(line.tax_id.amount))  # noqa
                temp[line.tax_id.description]['valRetAir'] += '%.2f' % abs(line.amount)
        for k, v in temp.items():
            data_air.append(v)
        #print(data_air)
        if data_air:
            return data_air[0]
        else:
            return {
                'baseImpAir': '%.2f' % baseImponible,
                'codRetAir': '332',
                'porcentajeAir': '0.00',
                'valRetAir': '0.00'
            }

    @api.model
    def _get_ventas(self, period):
        sql_ventas = "SELECT type, sum(amount_vat+amount_vat_cero+amount_novat) AS base \
                      FROM account_invoice \
                      WHERE type IN ('out_invoice', 'out_refund') \
                      AND state IN ('open','paid') \
                      AND date BETWEEN '%s' AND '%s'" % (
                        period.date_start,
                        period.date_stop
                        )
        sql_ventas += " GROUP BY type"
        self.env.cr.execute(sql_ventas)
        res = self.env.cr.fetchall()
        resultado = sum(map(lambda x: x[0] == 'out_refund' and x[1] * -1 or x[1], res))  # noqa
        return resultado

    def _get_ret_iva(self, invoice):
        """
        Return (valRetBien10, valRetServ20,
        valorRetBienes,
        valorRetServicios, valorRetServ100)
        """
        retBien10 = 0
        retServ20 = 0
        retBien = 0
        retServ = 0
        retServ100 = 0
        for tax in invoice.tax_line_ids:
            if tax.group_id.code == 'ret_vat_b':
                if tax.percent_report == '10':
                    retBien10 += abs(tax.amount)
                else:
                    retBien += abs(tax.amount)
            if tax.group_id.code == 'ret_vat_srv':
                if tax.percent_report == '100':
                    retServ100 += abs(tax.amount)
                elif tax.percent_report == '20':
                    retServ20 += abs(tax.amount)
                else:
                    retServ += abs(tax.amount)
        return retBien10, retServ20, retBien, retServ, retServ100

    def get_withholding(self, wh):
        autRetencion1 = ''
        if wh.auth_inv_id.is_electronic:
            autRetencion1 = wh.clave_acceso
        else:
            autRetencion1 = wh.auth_inv_id.name
        return {
            'estabRetencion1': wh.auth_inv_id.serie_entidad,
            'ptoEmiRetencion1': wh.auth_inv_id.serie_emision,
            'secRetencion1': wh.name[6:15],
            'autRetencion1': autRetencion1,
            'fechaEmiRet1': convertir_fecha(wh.date)
        }

    def get_refund(self, invoice):
        refund = self.env['account.invoice'].search([
            ('number', '=', invoice.origin)
        ])
        if refund:
            #auth = refund.auth_inv_id
            return {
                'docModificado': '01',
                'estabModificado': refund[0].invoice_number[0:3],
                'ptoEmiModificado': refund.invoice_number[3:6],
                'secModificado': refund.supplier_invoice_number,
                'autModificado': refund.reference,
            }
        else:
            auth = refund.auth_inv_id
            return {
                'docModificado': auth.type_id.code,
                'estabModificado': auth.serie_entidad,
                'ptoEmiModificado': auth.serie_emision,
                'secModificado': refund.invoice_number[6:15],
                'autModificado': refund.reference
            }

    def get_reembolsos(self, invoice):
        if not invoice.auth_inv_id.type_id.code == '41':
            return False
        res = []
        for r in invoice.refund_ids:
            res.append({
                'tipoComprobanteReemb': r.doc_id.code,
                'tpIdProvReemb': tpIdProv[r.partner_id.type_id],
                'idProvReemb': r.partner_id.identifier,
                'establecimientoReemb': r.auth_inv_id.serie_entidad,
                'puntoEmisionReemb': r.auth_inv_id.serie_emision,
                'secuencialReemb': r.secuencial,
                'fechaEmisionReemb': convertir_fecha(r.date),
                'autorizacionReemb': r.auth_inv_id.name,
                'baseImponibleReemb': '0.00',
                'baseImpGravReemb': '0.00',
                'baseNoGravReemb': '%.2f' % r.amount,
                'baseImpExeReemb': '0.00',
                'montoIceRemb': '0.00',
                'montoIvaRemb': '%.2f' % r.tax
            })
        return res

    def read_compras(self, period):
        """
        Procesa:
          * facturas de proveedor
          * liquidaciones de compra
        """
        inv_obj = self.env['account.invoice']
        dmn_purchase = [
            ('state', 'in', ['open', 'paid']),
            ('date', '>=', period.date_start),
            ('date', '<=', period.date_stop),
            ('type', 'in', ['in_invoice', 'liq_purchase', 'in_refund'])  # noqa
        ]
        compras = []
        for inv in inv_obj.search(dmn_purchase):
            if not inv.partner_id.type_id == 'pasaporte':
                detallecompras = {}
                auth = inv.auth_inv_id
                valRetBien10, valRetServ20, valorRetBienes, valorRetServicios, valorRetServ100 = self._get_ret_iva(inv)  # noqa
                t_reeb = 0.0
                if not inv.auth_inv_id.type_id.code == '41':
                    t_reeb = 0.00
                else:
                    if inv.type == 'liq_purchase':
                        t_reeb = 0.0
                    else:
                        t_reeb = inv.amount_untaxed
                detallecompras.update({
                    'codSustento': inv.sustento_id.code,
                    'tpIdProv': tpIdProv[inv.partner_id.type_id],
                    'idProv': inv.partner_id.identifier,
                    'tipoComprobante': inv.type == 'liq_purchase' and '03' or auth.type_id.code,  # noqa
                    'parteRel': 'NO',
                    'fechaRegistro': convertir_fecha(inv.date_invoice),
                    'establecimiento': inv.invoice_number[:3],
                    'puntoEmision': inv.invoice_number[3:6],
                    'secuencial': inv.invoice_number[6:15],
                    'fechaEmision': convertir_fecha(inv.date_invoice),
                    'autorizacion': inv.auth_number,
                    'baseNoGraIva': '%.2f' % inv.amount_novat,
                    'baseImponible': '%.2f' % inv.amount_vat_cero,
                    'baseImpGrav': '%.2f' % inv.amount_vat,
                    'baseImpExe': '0.00',
                    'total': inv.amount_pay,
                    'montoIce': '0.00',
                    'montoIva': '%.2f' % inv.amount_tax,
                    'valRetBien10': '%.2f' % valRetBien10,
                    'valRetServ20': '%.2f' % valRetServ20,
                    'valorRetBienes': '%.2f' % valorRetBienes,
                    'valRetServ50': '0.00',
                    'valorRetServicios': '%.2f' % valorRetServicios,
                    'valorRetServ100': '%.2f' % valorRetServ100,
                    'totbasesImpReemb': '%.2f' % t_reeb,
                    'pagoExterior': {
                        'pagoLocExt': '01',
                        'paisEfecPago': 'NA',
                        'aplicConvDobTrib': 'NA',
                        'pagoExtSujRetNorLeg': 'NA'
                    },
                    'detalleAir': self.process_lines(inv.tax_line_ids, inv.amount_vat)
                })                

                if inv.retention_id:
                    detallecompras.update({'retencion': True})
                    detallecompras.update(self.get_withholding(inv.retention_id))  # noqa
                if inv.type in ['out_refund', 'in_refund']:
                    refund = self.get_refund(inv)
                    if refund:
                        detallecompras.update({'es_nc': True})
                        detallecompras.update(refund)
                detallecompras.update({
                    'reembolsos': self.get_reembolsos(inv)
                })
                compras.append(detallecompras)
        return compras

    @api.multi
    def read_ventas(self, period):
        dmn = [
            ('state', 'in', ['open', 'paid']),
            ('date', '>=', period.date_start),
            ('date', '<=', period.date_stop),
            ('type', '=', 'out_invoice'),
            ('auth_inv_id.is_electronic', '!=', True)
        ]
        ventas = []
        for inv in self.env['account.invoice'].search(dmn):
            detalleventas = {
                'tpIdCliente': tpIdCliente[inv.partner_id.type_id],
                'idCliente': inv.partner_id.identifier,
                'parteRelVtas': 'NO',
                'partner': inv.partner_id,
                'auth': inv.auth_inv_id,
                'tipoComprobante': inv.auth_inv_id.type_id.code,
                'tipoEmision': inv.auth_inv_id.is_electronic and 'E' or 'F',
                'numeroComprobantes': 1,
                'baseNoGraIva': inv.amount_novat,
                'baseImponible': inv.amount_vat_cero,
                'baseImpGrav': inv.amount_vat,
                'montoIva': inv.amount_tax,
                'montoIce': '0.00',
                'valorRetIva': (abs(inv.taxed_ret_vatb) + abs(inv.taxed_ret_vatsrv)),  # noqa
                'valorRetRenta': abs(inv.taxed_ret_ir),
                # 'formasDePago': {
                #     'formaPago': inv.payment_ids.code
                # }
            }

            #ventas.append(detalleventas)
            formasDePago = []
            for payment_id in inv.payment_ids:
                if payment_id.journal_id.epayment_id.code:
                    pago = {'formaPago' : payment_id.journal_id.epayment_id.code}
                    if pago not in formasDePago:
                        formasDePago.append(pago)

            detalleventas.update({'formasDePago':formasDePago})
            ventas.append(detalleventas)

        ventas = sorted(ventas, key=itemgetter('idCliente'))
        ventas_end = []
        for ruc, grupo in groupby(ventas, key=itemgetter('idCliente')):
            baseimp = 0
            nograviva = 0
            montoiva = 0
            retiva = 0
            impgrav = 0
            retrenta = 0
            numComp = 0
            partner_temp = False
            auth_temp = False
            formasDePago = []
            for i in grupo:
                nograviva += i['baseNoGraIva']
                baseimp += i['baseImponible']
                impgrav += i['baseImpGrav']
                montoiva += i['montoIva']
                retiva += i['valorRetIva']
                retrenta += i['valorRetRenta']
                numComp += 1
                partner_temp = i['partner']
                auth_temp = i['auth']
                if i['formasDePago'] not in formasDePago:
                    for formaPago in i['formasDePago']:
                        if formaPago not in formasDePago:
                            formasDePago.append(formaPago)
            detalle = {
                'tpIdCliente': tpIdCliente[partner_temp.type_id],
                'idCliente': ruc,
                'parteRelVtas': 'NO',
                'tipoComprobante': auth_temp.type_id.code,
                'tipoEmision': auth_temp.is_electronic and 'E' or 'F',
                'numeroComprobantes': numComp,
                'baseNoGraIva': '%.2f' % nograviva,
                'baseImponible': '%.2f' % baseimp,
                'baseImpGrav': '%.2f' % impgrav,
                'montoIva': '%.2f' % montoiva,
                'montoIce': '0.00',
                'valorRetIva': '%.2f' % retiva,
                'valorRetRenta': '%.2f' % retrenta,
                'formasDePago': formasDePago
            }

            ventas_end.append(detalle)
        return ventas_end

    @api.multi
    def read_anulados(self, period):
        dmn = [
            ('state', '=', 'cancel'),
            ('date', '>=', period.date_start),
            ('date', '<=', period.date_stop),
            ('type', 'in', ['out_invoice', 'liq_purchase'])
        ]
        anulados = []
        for inv in self.env['account.invoice'].search(dmn):
            auth = inv.auth_inv_id
            aut = auth.is_electronic and inv.numero_autorizacion or auth.name
            detalleanulados = {
                'tipoComprobante': auth.type_id.code,
                'establecimiento': auth.serie_entidad,
                'ptoEmision': auth.serie_emision,
                'secuencialInicio': inv.invoice_number[6:9],
                'secuencialFin': inv.invoice_number[6:9],
                'autorizacion': aut
            }
            anulados.append(detalleanulados)

        dmn_ret = [
            ('state', '=', 'cancel'),
            ('date', '>=', period.date_start),
            ('date', '<=', period.date_stop),
            ('in_type', '=', 'ret_in_invoice')
        ]
        for ret in self.env['account.retention'].search(dmn_ret):
            auth = ret.auth_id
            aut = auth.is_electronic and inv.numero_autorizacion or auth.name
            detalleanulados = {
                'tipoComprobante': auth.type_id.code,
                'establecimiento': auth.serie_entidad,
                'ptoEmision': auth.serie_emision,
                'secuencialInicio': ret.name[6:9],
                'secuencialFin': ret.name[6:9],
                'autorizacion': aut
            }
            anulados.append(detalleanulados)
        return anulados

    @api.multi
    def render_xml(self, ats):
        tmpl_path = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_path))
        ats_tmpl = env.get_template('ats.xml')
        return ats_tmpl.render(ats)

    @api.multi
    def validate_document(self, ats, error_log=False):
        file_path = os.path.join(os.path.dirname(__file__), 'XSD/ats.xsd')
        schema_file = open(file_path)
        xmlschema_doc = etree.parse(schema_file)
        xmlschema = etree.XMLSchema(xmlschema_doc)
        root = etree.fromstring(ats)
        ok = True
        if not self.no_validate:
            try:
                xmlschema.assertValid(root)
            except DocumentInvalid:
                ok = False
        return ok, xmlschema

    @api.multi
    def act_export_ats(self):
        ats = AccountAts()
        period = self.period_id
        ruc = self.company_id.partner_id.identifier
        ats.TipoIDInformante = 'R'
        ats.IdInformante = ruc
        ats.razonSocial = self.company_id.name.upper()
        ats.Anio = get_date_value(period.date_start, '%Y')
        ats.Mes = get_date_value(period.date_start, '%m')
        ats.numEstabRuc = self.num_estab_ruc.zfill(3)
        ats.AtstotalVentas = '%.2f' % self._get_ventas(period)
        ats.totalVentas = '%.2f' % self._get_ventas(period)
        ats.codigoOperativo = 'IVA'
        ats.compras = self.read_compras(period)
        ats.ventas = self.read_ventas(period)
        ats.codEstab = self.num_estab_ruc
        ats.ventasEstab = '%.2f' % self._get_ventas(period)
        ats.ivaComp = '0'
        ats.anulados = self.read_anulados(period)
        self._logger.info('ATS')
        ats_rendered = self.render_xml(ats)
        self._logger.debug(ats)
        ok, schema = self.validate_document(ats_rendered.encode())
        if not ok:
            raise UserError(schema.error_log)
        buf = io.BytesIO()
        buf.write(ats_rendered.encode())
        out = base64.encodestring(buf.getvalue())
        buf.close()
        buf_erro = io.BytesIO()
        for error in schema.error_log:
            buf_erro.write(error.message.encode())
        out_erro = base64.encodestring(buf_erro.getvalue())
        buf_erro.close()
        name = "%s%s%s.XML" % (
            "AT",
            period.name[:2],
            period.name[3:8]
        )
        data2save = {
            'state': ok and 'export' or 'export_error',
            'data': out,
            'fcname': name
        }
        if not ok:
            data2save.update({
                'error_data': out_erro,
                'fcname_errores': 'ERRORES.txt'
            })
        self.write(data2save)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.ats',
            'view_mode': ' form',
            'view_type': ' form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'self',
        }

    fcname = fields.Char('Nombre de Archivo', size=50, readonly=True)
    fcname_errores = fields.Char('Archivo Errores', size=50, readonly=True)
    period_id = fields.Many2one(
        'account.period',
        'Periodo',
        default=_get_period
    )
    company_id = fields.Many2one(
        'res.company',
        'Compania',
        default=_get_company
    )
    num_estab_ruc = fields.Char(
        'Num. de Establecimientos',
        size=3,
        required=True,
        default='001'
    )
    pay_limit = fields.Float('Limite de Pago', default=1000)
    data = fields.Binary('Archivo XML')
    error_data = fields.Binary('Archivo de Errores')
    no_validate = fields.Boolean('No Validar')
    state = fields.Selection(
        (
            ('choose', 'Elegir'),
            ('export', 'Generado'),
            ('export_error', 'Error')
        ),
        string='Estado',
        default='choose'
    )
