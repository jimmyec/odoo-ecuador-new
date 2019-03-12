#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unicodedata
from collections import OrderedDict
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Refund
    'in_refund': 'in_invoice',          # Vendor Refund
}

RET_COMPRAS = [
    'RetAir', 'RetIva', 'RetBien10',
    'RetBienes', 'RetServ50', 'RetServ100',
    'RetServ20', 'RetServicios'
]

RET_VENTAS = [
    'RetIva', 'RetRenta'
]

BASES_IMPONIBLES = [
    'ImpExe', 'ImpGrav', 'Imponible',
    'Reembolso', 'NoGraIva'
]


class AccountInvoice(models.Model):
    _inherit = ['account.invoice']

    def normalize_text(self, s, result='unicode'):
        remove = ['Mn', 'Po', 'Pc', 'Pd', 'Pf', 'Pi', 'Ps']
        res = ''.join((
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) not in remove
        ))

        return res

    def normalize_date(self, date, fmt='dmy'):
        if fmt == 'dmy':
            return datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')

    @api.multi
    def get_sri_secuencial_completo_factura(self):
        """
        Obtiene el secuencial completo del documento principal,
        se usa para facturas y notas de crédito.
        """
        return '-'.join([
            self.establecimiento or '0',
            self.puntoemision or '0',
            (self.secuencial or '0').zfill(9)
        ])

    @api.multi
    def get_sri_secuencial_completo_retencion(self):
        return '-'.join([
            self.estabretencion1 or '0',
            self.ptoemiretencion1 or '0',
            (self.secretencion1 or '0').zfill(9)
        ])

    @api.multi
    def get_sri_secuencial_completo_guia(self):
        nro_guia = ''

        # Falla sin el modulo stock_picking_invoice_link.
        try:
            nro_guia = ' '.join([
                p.get_sri_secuencial_completo_guia() for p in self.picking_ids
            ])
        except:
            pass
        return nro_guia

    @api.multi
    def get_sri_cero_iva(self):
        """
        Si la linea no tiene retención de IVA creamos un impuesto con
        IVA 0% para el xml de retenciones de venta en facturación electrónica.

        No se requiere en compras.
        """
        # TODO: permitir elegir el impuesto por defecto en la configuración de la compañía.
        for inv in self:
            for line in inv.invoice_line_ids:
                base = sum(
                    t.base for t in line.sri_tax_line_ids if t.group == 'RetIva')
                residual = line.price_subtotal - base
                if round(residual, 2) > 0:
                    self.env['l10n_ec_sri.tax.line'].create({
                        'invoice_line_id': line.id,
                        'formulario': 'NA',
                        'campo': 'NA',
                        'group': 'RetIva',
                        'amount': 0.0,
                        'base': residual,
                        'porcentaje': '0',
                        'impuesto': 'RET. IVA 0%',
                        'codigo': '2',
                        'codigoporcentaje': '7',
                    })

    @api.multi
    def get_sri_cero_air(self):
        """
        En caso de haber valores no declarados en el formulario 103
        Creamos un impuesto en el campo 332 por retención 0% general.
        :return:
        """
        # TODO: permitir elegir el impuesto por defecto en la configuración de la compañía.
        for inv in self:
            for line in inv.invoice_line_ids:

                # Agregamos el 332 solo si hay una base imponible.
                if not any(
                        tax.tax_group_id.name in BASES_IMPONIBLES
                        for tax in line.invoice_line_tax_ids):
                    continue

                # La base es la diferencia entre las bases existentes
                # y el subtotal para cubrir casos como el 322.
                base = sum(
                    t.base for t in line.sri_tax_line_ids
                    if t.group == 'RetAir'
                )
                residual = line.price_subtotal - base
                if round(residual, 2) > 0:
                    self.env['l10n_ec_sri.tax.line'].create({
                        'invoice_line_id': line.id,
                        'formulario': '103',
                        'campo': '332',
                        'group': 'RetAir',
                        'amount': 0.0,
                        'base': residual,
                        'porcentaje': '0',
                        'impuesto': '332',
                        'codigo': '1',
                        'codigoporcentaje': '332',
                    })

    @api.multi
    def get_sri_ats_lines(self):
        for inv in self:
            # Limpia líneas de ATS anteriormente calculadas
            inv.sri_ats_line_ids.unlink()

            # Hacemos una lista de los sustentos de la factura.
            sustentos = inv.invoice_line_ids.mapped(
                'invoice_line_tax_ids').mapped('sustento_id.code')

            if not sustentos and inv.type in ['out_invoice', 'out_refund']:
                # Utilizamos 'NA' para generar líneas del ATS en ventas.
                sustentos = ['NA']

            # Diccionario para crear la línea de ATS en la factura.
            sri_ats_lines = []

            for s in sustentos:
                basenograiva = 0.0
                baseimponible = 0.0
                baseimpgrav = 0.0
                baseimpexe = 0.0
                montoice = 0.0
                montoiva = 0.0
                valretbien10 = 0.0
                valretserv20 = 0.0
                valretserv50 = 0.0
                valorretbienes = 0.0
                valorretservicios = 0.0
                valretserv100 = 0.0
                valorretiva = 0.0
                valorretrenta = 0.0

                detalleair = []

                for line in inv.invoice_line_ids:
                    codsustento = line.mapped('invoice_line_tax_ids').mapped(
                        'sustento_id.code') or ['NA']
                    if codsustento and codsustento[0] == s:
                        for tl in line.sri_tax_line_ids:
                            # AGREGAMOS LAS BASES DE IMPUESTO SEGÚN CORRESPONDE.
                            if tl.group == 'NoGraIva':
                                basenograiva += tl.base
                            elif tl.group == 'Imponible':
                                baseimponible += tl.base
                            elif tl.group == 'ImpGrav':
                                baseimpgrav += tl.base
                                # Solamente el grupo ImpGrav genera valores en montoiva
                                montoiva += tl.amount
                            elif tl.group == 'ImpExe':
                                baseimpexe += tl.base
                            # RETENCIONES DE COMPRAS.
                            elif tl.group == 'RetBien10':
                                valretbien10 += tl.amount
                            elif tl.group == 'RetServ20':
                                valretserv20 += tl.amount
                            elif tl.group == 'RetServ50':
                                valretserv50 += tl.amount
                            elif tl.group == 'RetBienes':
                                valorretbienes += tl.amount
                            elif tl.group == 'RetServicios':
                                valorretservicios += tl.amount
                            elif tl.group == 'RetServ100':
                                valretserv100 += tl.amount
                            # RETENCIONES EN VENTAS.
                            elif tl.group == 'RetIva':
                                valorretiva += tl.amount
                            elif tl.group == 'RetRenta':
                                valorretrenta += tl.amount
                            # AGREGAMOS EL VALOR DEL ICE.
                            elif tl.group == 'Ice':
                                montoice += tl.amount

                            # HACEMOS LOS DICCIONARIOS DE RETENCIONES DE IR.
                            elif tl.group == 'RetAir':

                                # Buscamos una línea de retención con el mismo código.
                                air = next(
                                    (item for item in detalleair if item["codretair"] == tl.impuesto), False)

                                if not air:
                                    # Agregamos el diccionario, no se agrega directamente con 0,0 porque
                                    # al hacerlo, falla la búsqueda anterior.
                                    detalleair.append({
                                        'valretair': abs(tl.amount),
                                        'baseimpair': tl.base,
                                        'codretair': tl.impuesto,
                                        'porcentajeair': tl.porcentaje,
                                    })
                                else:
                                    air['baseimpair'] += tl.base
                                    air['valretair'] += abs(tl.amount)

                # Agregamos 0,0 a la lista para que Odoo cree las líneas, no poner 0,0 directamente.
                detalleair_line = []
                for air in detalleair:
                    detalleair_line.append((0, 0, air))

                sri_ats_lines.append({
                    'invoice_id': inv.id,
                    'codsustento': s,
                    'basenograiva': abs(basenograiva),
                    'baseimponible': abs(baseimponible),
                    'baseimpgrav': abs(baseimpgrav),
                    'baseimpexe': abs(baseimpexe),
                    'montoice': abs(montoice),
                    'montoiva': abs(montoiva),
                    'valretbien10': abs(valretbien10),
                    'valretserv20': abs(valretserv20),
                    'valretserv50': abs(valretserv50),
                    'valorretbienes': abs(valorretbienes),
                    'valorretservicios': abs(valorretservicios),
                    'valretserv100': abs(valretserv100),
                    'valorretiva': abs(valorretiva),
                    'valorretrenta': abs(valorretrenta),
                    'detalleair_ids': detalleair_line,
                })

            for l in sri_ats_lines:
                self.env['l10n_ec_sri.ats.line'].create(l)

    @api.multi
    def button_prepare_sri_declaration(self):
        for inv in self:

            # Genera las lineas de impuestos y ats en compras y ventas.
            lines = inv.get_sri_tax_lines()
            for line in lines:
                self.env['l10n_ec_sri.tax.line'].create(line)

            # Aplicar solo en compras.
            # Antes de get_sri_ats_lines y consolidate_sri_tax_lines.
            if inv.type in ('in_refund', 'in_invoice'):
                inv.get_sri_cero_air()

            # Aplicar solo en ventas.
            if inv.type in ('out_refund', 'out_invoice'):
                inv.get_sri_cero_iva()

            # Consolida las lineas de impuestos en compras y ventas.
            inv.consolidate_sri_tax_lines()

            # Se debe ejecutar luego de las anteriores para tener todos los impuestos.
            inv.get_sri_ats_lines()

    @api.multi
    def consolidate_sri_tax_lines(self):
        """
        Crea un consolidado de impuestos en la factura para
        permitir la revisión de impuestos por parte del contador.

        :return:
        """
        for inv in self:
            # Limpiamos las líneas de impuestos previamente creados.
            inv.sri_tax_line_ids.unlink()

            sri_tax_lines = []

            lines = self.invoice_line_ids.mapped('sri_tax_line_ids')
            for line in lines:
                tax_line = next(
                    (item for item in sri_tax_lines
                     if item['formulario'] == line.formulario
                     and item['campo'] == line.campo), False)

                if not tax_line:
                    sri_tax_lines.append({
                        'invoice_id': inv.id,
                        'formulario': line.formulario,
                        'campo': line.campo,
                        'group': line.group,
                        'amount': abs(line.amount),
                        'base': line.base,
                        'porcentaje': line.porcentaje,
                        'impuesto': line.impuesto,
                        'codigo': line.codigo,
                        'codigoporcentaje': line.codigoporcentaje,
                        'gap': line.gap,
                    })
                else:
                    tax_line['amount'] += abs(line.amount)
                    tax_line['base'] += abs(line.base)

            for l in sri_tax_lines:
                self.env['l10n_ec_sri.tax.line'].create(l)

    @api.multi
    def prepare_detallecompras_dict(self):
        """
        Genera un diccionario para la creación del ATS.
        :return: Consolidado de detallecompras para el ATS
        """
        for inv in self:
            partner = inv.partner_id
            fiscal = partner.property_account_position_id
            # La fecha de registro debe ser del mismo mes que la factura,
            # si es un mes distinto, se declara la fecha de la factura.
            # TODO según el SRI debería ser el último día del mes.
            if inv.date_invoice[5:7] != inv.date[5:7]:
                fechaRegistro = inv.date_invoice
            else:
                fechaRegistro = inv.date

            # Calcula la fecha de emisión de la retención.
            if inv.fechaemiret1:
                fechaEmiRet1 = datetime.strptime(
                    inv.fechaemiret1, '%Y-%m-%d').strftime('%d/%m/%Y')
            else:
                fechaEmiRet1 = ''

            # Normaliza las autorizaciones en caso de documentos que no requieren autorización.
            if not inv.comprobante_id.requiere_autorizacion:
                establecimiento = inv.establecimiento or '999'
                puntoEmision = inv.puntoemision or '999'

                if int(inv.secuencial) < 1:
                    secuencial = '999999999'
                else:
                    secuencial = inv.secuencial or '999999999'

                if int(inv.autorizacion) < 1:
                    autorizacion = '9999999999'
                else:
                    autorizacion = inv.autorizacion or '9999999999'

            else:
                establecimiento = inv.establecimiento
                puntoEmision = inv.puntoemision
                secuencial = inv.secuencial
                autorizacion = inv.autorizacion

            # TODO Diccionario de la forma de pago.
            pagoExterior = []

            tipopago = str(fiscal.tipopago_id.code)
            if tipopago == '01':
                pagoExterior.append(OrderedDict([
                    ('pagoLocExt', tipopago),
                    ('paisEfecPago', 'NA'),
                    ('aplicConvDobTrib', 'NA'),
                    ('pagExtSujRetNorLeg', 'NA'),
                    ('pagoRegFis', 'NA'),
                ]))
            else:
                pagoExterior.append(OrderedDict([
                    ('pagoLocExt', tipopago),
                    ('paisEfecPago', partner.country_id.code),
                    ('aplicConvDobTrib', fiscal.doble_tributacion and 'SI' or 'NO'),
                    ('pagExtSujRetNorLeg', 'DUMMIE'),
                    ('pagoRegFis', 'DUMMIE'),
                ]))

            # Formas de pago.
            formaPago = []
            if inv.total > 1000:
                # Si el total de la factura es mayor a 1000
                # debe tener forma de pago.

                # Por ello, agregamos el código de todos los pagos.
                formaPago = inv.payment_ids.mapped('formapago_id.code')
                if not formaPago:
                    # O la forma por defecto en el partner.
                    formaPago.append(partner.formapago_id.code)
                if not formaPago:
                    # O la forma por defecto en el diario de compra.
                    formaPago.append(inv.journal_id.formapago_id.code)
                if not formaPago:
                    # O "con utilización del sistema financiero".
                    formaPago.append('20')
            detalleCompras = []

            for line in inv.sri_ats_line_ids:
                # Detalle de retenciones de impuesto a la renta.
                detalleAir = []
                for air in line.detalleair_ids:
                    detalleAir.append(OrderedDict([
                        ('codRetAir', air.codretair),
                        ('baseImpAir', '{:.2f}'.format(air.baseimpair)),
                        ('porcentajeAir', air.porcentajeair),
                        ('valRetAir', '{:.2f}'.format(air.valretair)),
                    ]))

                vals = (OrderedDict([
                    ('codSustento', line.codsustento),
                    ('tpIdProv', fiscal.identificacion_id.tpidprov),
                    ('idProv', partner.vat),
                    ('tipoComprobante', inv.comprobante_id.code),
                    ('parteRel', partner.parterel and 'SI' or 'NO'),
                    ('fechaRegistro', inv.normalize_date(fechaRegistro)),
                    ('establecimiento', establecimiento),
                    ('puntoEmision', puntoEmision),
                    ('secuencial', secuencial),
                    ('fechaEmision', inv.normalize_date(inv.date_invoice)),
                    ('autorizacion', autorizacion),
                    ('baseNoGraIva', '{:.2f}'.format(
                        line.basenograiva or 0.00)),
                    ('baseImponible', '{:.2f}'.format(
                        line.baseimponible or 0.00)),
                    ('baseImpGrav', '{:.2f}'.format(line.baseimpgrav or 0.00)),
                    ('baseImpExe', '{:.2f}'.format(line.baseimpexe or 0.00)),
                    ('montoIce', '{:.2f}'.format(line.montoice or 0.00)),
                    ('montoIva', '{:.2f}'.format(line.montoiva or 0.00)),
                    ('valRetBien10', '{:.2f}'.format(
                        line.valretbien10 or 0.00)),
                    ('valRetServ20', '{:.2f}'.format(
                        line.valretserv20 or 0.00)),
                    ('valorRetBienes', '{:.2f}'.format(
                        line.valorretbienes or 0.00)),
                    ('valRetServ50', '{:.2f}'.format(
                        line.valretserv50 or 0.00)),
                    ('valorRetServicios', '{:.2f}'.format(
                        line.valorretservicios or 0.00)),
                    ('valRetServ100', '{:.2f}'.format(
                        line.valretserv100 or 0.00)),
                    # ('pagoLocExt', fiscal.tipopago_id.code), # TODO
                    ('totbasesImpReemb', '{:.2f}'.format(0.00)),  # TODO
                    ('pagoExterior', pagoExterior),
                ]))

                if formaPago:
                    vals.update(OrderedDict([
                        ('formasDePago', {'formaPago': formaPago}),
                    ]))

                vals.update(OrderedDict([
                    ('air', {'detalleAir': detalleAir}),
                ]))

                if inv.secretencion1:
                    vals.update(OrderedDict([
                        ('estabRetencion1', inv.estabretencion1 or ''),
                        ('ptoEmiRetencion1', inv.ptoemiretencion1 or ''),
                        ('secRetencion1', inv.secretencion1 or ''),
                        ('autRetencion1', inv.autretencion1 or ''),
                        ('fechaEmiRet1', inv.normalize_date(
                            inv.fechaemiret1 or inv.date_invoice)),
                    ]))

                if fiscal.identificacion_id.code == 'P':
                    vals.update(
                        OrderedDict([
                            ('tipoProv', inv.persona_id.tipoprov),
                        ])
                    )

                if inv.reembolso_ids:
                    reembolsos = []
                    for r in inv.reembolso_ids.mapped('sri_ats_line_ids'):
                        r_inv = r.invoice_id
                        r_partner = r_inv.partner_id
                        r_fiscal = r_partner.property_account_position_id

                        reembolsos.append(OrderedDict([
                            ('tipoComprobanteReemb', r_inv.comprobante_id.code),
                            ('tpIdProvReemb', r_fiscal.identificacion_id.tpidprov),
                            ('idProvReemb', r_partner.vat),
                            ('establecimientoReemb', r_inv.establecimiento),
                            ('puntoEmisionReemb', r_inv.puntoemision),
                            ('secuencialReemb', r_inv.secuencial),
                            ('fechaEmisionReemb', r_inv.normalize_date(
                                r_inv.date_invoice)),
                            ('autorizacionReemb', r_inv.autorizacion),
                            ('baseImponibleReemb',
                             '{:.2f}'.format(r.baseimponible)),
                            ('baseImpGravReemb',
                             '{:.2f}'.format(r.baseimpgrav)),
                            ('baseNoGraIvaReemb',
                             '{:.2f}'.format(r.basenograiva)),
                            ('baseImpExeReemb', '{:.2f}'.format(r.baseimpexe)),
                            ('montoIceRemb', '{:.2f}'.format(r.montoice)),
                            ('montoIvaRemb', '{:.2f}'.format(r.montoiva)),
                        ]))

                    vals.update(
                        OrderedDict([
                            ('reembolsos', reembolsos),
                        ])
                    )

                if inv.origin_invoice_ids:
                    mod = inv.origin_invoice_ids[0]
                    vals.update(OrderedDict([
                        ('docModificado', mod.comprobante_id.code),
                        ('estabModificado', mod.establecimiento),
                        ('ptoEmiModificado', mod.puntoemision),
                        ('secModificado', mod.secuencial),
                        ('autModificado', mod.autorizacion),
                    ]))

                detalleCompras.append(vals)

            return detalleCompras

    @api.multi
    def get_sri_tax_lines(self):
        for inv in self:
            # Datos para crear los impuestos en las líneas
            sri_tax_lines = []

            # Los impuestos de la factura, en diccionario.
            inv_taxes = []

            # Debemos procesar cada impuesto una sola vez.
            taxes_set = inv.tax_line_ids.mapped('tax_id')

            # Seleccionamos una línea por cada impuesto para usarla de base.
            unique_tax_lines = self.env['account.invoice.tax']
            for t in taxes_set:
                unique_tax_lines += inv.tax_line_ids.filtered(
                    lambda x: x.tax_id == t)[0]

            # Obtenemos la información de los impuestos de la factura para hacer el cuadre.
            for tax_line in unique_tax_lines:
                tax = tax_line.tax_id

                # Calcula en cuántas líneas es utilizado el impuesto.
                nro = len(inv.invoice_line_ids.filtered(
                    lambda l: tax in l.invoice_line_tax_ids))

                # Dado que se va a procesar una sola línea por cada impuesto
                # obtenemos el valor todal de dicho impuesto sumando los valores
                # de todas las líneas de dicho impuesto.
                amount = sum(inv.tax_line_ids.filtered(
                    lambda l: tax == l.tax_id).mapped('amount'))

                # Obtenemos el formulario desde los tag.
                formulario, campo = tax.get_data_from_tag(tax.tag_ids)

                # Genera un diccionario con los impuestos de la factura.
                inv_taxes.append({
                    'id': tax.id,
                    'formulario': formulario,
                    'campo': campo,
                    'amount': amount,
                    'group': tax.tax_group_id.name,
                    'porcentaje': str(abs(int(tax.amount))) or '0',
                    'impuesto': tax.impuesto,
                    'codigo': tax.codigo,
                    'codigoporcentaje': tax.codigoporcentaje,
                    'nro': nro,
                })

            # Ordena las líneas de menor a mayor para aplicar la diferencia a la línea con mayor valor.
            lines = inv.invoice_line_ids.sorted(lambda x: x.price_subtotal)

            for line in lines:

                # Limpia líneas de impuestos anteriormente calculadas
                line.sri_tax_line_ids.unlink()
                currency = line.invoice_id and line.invoice_id.currency_id or None

                # Usamos el método de cálculo estándar de Odoo para evitar conflictos en el redondeo.
                price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)

                tax_obj = line.invoice_line_tax_ids.compute_all(
                    price_unit,
                    currency=currency,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=inv.partner_id
                )

                # Selecciona los impuestos de la línea en diccionario.
                taxes = sorted(tax_obj['taxes'], key=lambda k: k['sequence'])

                baseimpgrav = 0
                # Repasamos cada impuesto calculado en los impuestos de la línea.
                for lt in taxes:  # .lower().sort(key=lambda x: x['sequence'])
                    gap = 0
                    for t in inv_taxes:

                        if lt['id'] == t['id']:

                            # REGULARIZAMOS LA BASE DEL IMPUESTO.
                            # Por defecto, la base es igual al price_subtotal de la línea.
                            base = line.price_subtotal
                            # Para las retenciones del IVA, buscamos un impuesto ImpGrav
                            if t['group'] in ('RetBien10', 'RetServ20', 'RetServ50', 'RetBienes', 'RetServicios', 'RetServ100', 'RetIva'):
                                base = baseimpgrav
                                #base_id = line.invoice_line_tax_ids.filtered(lambda t: t.tax_group_id.name == 'ImpGrav').id
                                #base = next((item for item in taxes if item['id'] == base_id), False)['amount'] or 0
                            # Para el impuesto 322 debemos tener como base el 10% del price_subtotal.
                            elif t['impuesto'] == '322':
                                base = round(line.price_subtotal * 0.1, 2)

                            # Si es la última línea en la que se usa el impuesto
                            # usamos como impuesto el valor restante, no el calculado.
                            # Registramos la diferencia en el campo gap para revisión.

                            if t['nro'] == 1:
                                if lt['amount'] != t['amount']:
                                    gap = t['amount'] - lt['amount']
                                line_amount = t['amount']
                            else:
                                line_amount = lt['amount']

                            # Agregamos el impuesto a un diccionario que se usará para crear las líneas de impuestos.
                            sri_tax_lines.append({
                                'invoice_line_id': line.id,
                                'formulario': t['formulario'],
                                'campo': t['campo'],
                                'group': t['group'],
                                'amount': abs(line_amount),
                                'base': base,
                                'porcentaje': t['porcentaje'],
                                'impuesto': t['impuesto'],
                                'codigo': t['codigo'],
                                'codigoporcentaje': t['codigoporcentaje'],
                                'gap': gap,
                            })
                            # Restamos el valor del impuesto de la línea del de la factura.
                            t['amount'] -= line_amount
                            # Reducimos la línea en uno, para idenfificar la última línea que usa el impuesto.
                            t['nro'] -= 1

                            # Si el impuesto es de IvaGrav, guardamos la base.
                            if t['group'] == 'ImpGrav':
                                baseimpgrav = abs(line_amount)

                # Obtenemos los id de todos los impuestos con valor.
                t_ids = inv.tax_line_ids.mapped('tax_id').ids

                # Repasamos todos los impuestos en búsqueda de impuestos en cero.
                for tax in line.invoice_line_tax_ids:
                    if tax.id not in t_ids:
                        # Si no están en la lista de impuestos con valor
                        # Los agregamos con valor cero y base igual al price_subtotal de la línea.

                        formulario, campo = tax.get_data_from_tag(tax.tag_ids)
                        sri_tax_lines.append({
                            'invoice_line_id': line.id,
                            'formulario': formulario,
                            'campo': campo,
                            'group': tax.tax_group_id.name,
                            'amount': 0.0,
                            'base': line.price_subtotal,
                            'porcentaje': str(abs(int(tax.amount))) or '0',
                            'impuesto': tax.impuesto,
                            'codigo': tax.codigo,
                            'codigoporcentaje': tax.codigoporcentaje,
                        })
            return sri_tax_lines

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        res = super(AccountInvoice, self)._onchange_invoice_line_ids()
        self.compute_sri_invoice_amounts()
        return res

    @api.multi
    def compute_sri_invoice_amounts(self):

        tax_lines = self.tax_line_ids
        inv_lines = self.invoice_line_ids

        # Desde las líneas de factura para detectar impuestos sin valor.
        impgrav_lines = inv_lines.filtered(
            lambda l: 'ImpGrav' in l.invoice_line_tax_ids.mapped('tax_group_id.name'))
        baseimpgrav = sum(line.price_subtotal for line in impgrav_lines) or 0

        # Restamos las líneas para obtener el valor no declarado.
        inv_lines -= impgrav_lines

        nograiva_lines = inv_lines.filtered(
            lambda l: 'NoGraIva' in l.invoice_line_tax_ids.mapped('tax_group_id.name'))
        basenograiva = sum(line.price_subtotal for line in nograiva_lines) or 0
        inv_lines -= nograiva_lines

        imponible_lines = inv_lines.filtered(
            lambda l: 'Imponible' in l.invoice_line_tax_ids.mapped('tax_group_id.name'))
        baseimponible = sum(
            line.price_subtotal for line in imponible_lines) or 0
        inv_lines -= imponible_lines

        impexe_lines = inv_lines.filtered(
            lambda l: 'ImpExe' in l.invoice_line_tax_ids.mapped('tax_group_id.name'))
        baseimpexe = sum(line.price_subtotal for line in impexe_lines) or 0
        inv_lines -= impexe_lines

        no_declarado = sum(line.price_subtotal for line in inv_lines) or 0

        # Desde las líneas de impuesto pues requerimos el valor.
        montoiva = sum(
            line.amount for line in tax_lines if line.tax_id.tax_group_id.name == 'ImpGrav')
        montoice = sum(
            line.amount for line in tax_lines if line.tax_id.tax_group_id.name == 'Ice')

        # Campos informativos de uso interno.
        subtotal = basenograiva + baseimponible + baseimpgrav + baseimpexe
        total = subtotal + montoiva + montoice

        self.update({
            'basenograiva': basenograiva,
            'baseimponible': baseimponible,
            'baseimpgrav': baseimpgrav,
            'baseimpexe': baseimpexe,
            'montoiva': montoiva,
            'montoice': montoice,
            'subtotal': subtotal,
            'total': total,
            'no_declarado': no_declarado,
        })

    sri_ats_line_ids = fields.One2many(
        'l10n_ec_sri.ats.line', inverse_name='invoice_id',
        string="Línea de ATS", )

    sri_tax_line_ids = fields.One2many(
        'l10n_ec_sri.tax.line', inverse_name='invoice_id',
        string='SRI Tax lines', )

    """
    in_inv_tax_form_set_ids = fields.Many2many(
        'l10n_ec_sri.tax.form.set', 'in_inv_sri_tax_form_set_rel', 'in_inv_form_set_ids',
        'in_invoice_ids', string="Tax form", )
    out_inv_tax_form_set_ids = fields.Many2many(
        'l10n_ec_sri.tax.form.set', 'out_inv_sri_tax_form_set_rel', 'out_inv_form_set_ids',
        'in_invoice_ids', string="Tax form", )
    in_ref_tax_form_set_ids = fields.Many2many(
        'l10n_ec_sri.tax.form.set', 'in_ref_sri_tax_form_set_rel', 'in_ref_form_set_ids',
        'in_refund_ids', string="Tax form", )
    out_ref_tax_form_set_ids = fields.Many2many(
        'l10n_ec_sri.tax.form.set', 'out_ref_sri_tax_form_set_rel', 'out_ref_form_set_ids',
        'out_refund_ids', string="Tax form", )
    """

    @api.multi
    def _default_date_invoice(self):
        return fields.Date.from_string(datetime.now().strftime('%Y-%m-%d'))

    state = fields.Selection(selection_add=[('reembolso', 'Reembolso')])

    @api.multi
    def button_marcar_reembolso(self):
        for inv in self:
            inv.state = 'reembolso'

    documento_reembolsado_ids = fields.Many2many(
        'account.invoice', 'invoice_reembolso_rel', 'documento_reembolsado_ids',
        'reembolso_ids', string="Documentos reembolsados", )
    reembolso_ids = fields.Many2many(
        'account.invoice', 'invoice_reembolso_rel', 'reembolso_ids',
        'documento_reembolsado_ids', string="Reembolsos",
        domain=[('state', '=', 'reembolso')], )

    comprobante_id = fields.Many2one(
        'l10n_ec_sri.comprobante', string='Comprobante', copy=False, )
    secuencial = fields.Char(
        string='Secuencial', copy=False, index=True,
        help="En caso de no tener secuencia, debe ingresar nueves, ejemplo: 999999.", )

    autorizacion_id = fields.Many2one(
        'l10n_ec_sri.autorizacion', string=u'Autorización', copy=False, )
    establecimiento = fields.Char('Establecimiento', copy=False, size=3, )
    puntoemision = fields.Char('Punto de emisión', copy=False, size=3, )
    autorizacion = fields.Char('Autorización', copy=False, )

    # PARA FACTURACIÓN ELECTRÓNICA
    # necesario en la base para declarar cuando es física.
    tipoem = fields.Selection(
        [
            ('F', 'Facturación física'),
            ('E', 'Facturación electrónica'),
        ],
        string='Tipo de emisión',
        default='F', )
        # Default F es importante para que las
        # facturas actuales sean todas físicas.

    def get_autorizacion(self):
        """
        Si el usuario tiene una autorización la usamos.
        Caso contrario usamos la de la compañía.
        """
        u = self.env.user
        c = self.company_id
        aut = tipo = False
        if self.type == 'out_invoice':
            aut = u.autorizacion_facturas_id or c.autorizacion_facturas_id
            tipo = 'f'
        elif self.type == 'in_invoice':
            if self.comprobante_id.code == '03':
                liq = u.autorizacion_liquidaciones_id or c.autorizacion_liquidaciones_id
                if liq.tipoem == 'E':
                    raise UserError(
                        _(u"Las liquidaciones de compras no pueden ser electrónicas"))
                self.set_liquidacion(liq)

            aut = u.autorizacion_retenciones_id or c.autorizacion_retenciones_id
            tipo = 'r'
            # Validamos si el valor de retenciones es mayor que cero.
            ret = self.sri_tax_line_ids.filtered(lambda r: r.group in (
                "RetAir", "RetBien10", "RetBienes", "RetIva", "RetServ100",
                "RetServ20", "RetServ50", "RetServicios"))
            ret_amount = sum(ret.mapped('amount'))
            if ret_amount <= 0:
                # Retornamos False para evitar
                # la generación de una retención.
                return False, False
        elif self.type == 'out_refund':
            aut = u.autorizacion_notas_credito_id or c.autorizacion_notas_credito_id
            tipo = 'nc'

        return aut, tipo

    @api.multi
    def set_liquidacion(self, aut):
        """
        Registra los valores en caso de liquidaciones de compra.
        Se realiza en un proceso independiente puesto que cuando
        existe una liquidación pueden haber dos documentos, la
        liquidación y la retención y la liquidación siempre es física.
        """
        secuencial = aut.secuencia_actual + 1
        self.update({
            'autorizacion_id': aut.id,
            'puntoemision': aut.puntoemision,
            'establecimiento': aut.establecimiento,
            'secuencial': secuencial,
            'tipoem': aut.tipoem,
            'comprobante_id': aut.comprobante_id.id,
        })
        aut.update({'secuencia_actual': secuencial})

    @api.multi
    def set_autorizacion(self):
        aut, tipo = self.get_autorizacion()

        if not aut:
            return aut, tipo

        # Si hay secuencial, lo utilizamos.
        # Y retornamos la autorización de la factura.
        if tipo in ('f', 'nc') and self.secuencial:
            return self.autorizacion_id, tipo
        # o la autorización de la retención.
        elif tipo == 'r' and self.secretencion1:
            return self.r_autorizacion_id, tipo

        # Si no hay secuencial, usamos la secuencia siguiente.
        secuencial = aut.secuencia_actual + 1

        # Actualizamos la autorización de acuerdo al tipo.
        if tipo in ('f', 'nc'):
            self.update({
                'autorizacion_id': aut.id,
                'puntoemision': aut.puntoemision,
                'establecimiento': aut.establecimiento,
                'secuencial': secuencial,
                'tipoem': aut.tipoem,
                'comprobante_id': aut.comprobante_id.id,
            })
        elif tipo == 'r' and aut:
            # Por defecto, ponemos la fecha de la retención
            # usando la de la factura.
            fecha = self.date_invoice

            self.update({
                'r_autorizacion_id': aut.id,
                'ptoemiretencion1': aut.puntoemision,
                'estabretencion1': aut.establecimiento,
                'secretencion1': secuencial,
                'fechaemiret1': fecha,
                'r_comprobante_id': aut.comprobante_id.id,
            })

        # Actualizamos la sencuencia en la autorización.
        aut.update({'secuencia_actual': secuencial})
        return aut, tipo

    def emision_documentos_electronicos(self, aut, tipo):
        """
        Función para sobreescribir.
        """
        return

    def emision_documentos_fisicos(self, aut, tipo):
        """
        En documentos físicos, solo colocamos el nro de autorización.
        """
        if tipo in ('f', 'nc'):
            self.autorizacion = aut.autorizacion
        elif tipo == 'r':
            self.autretencion1 = aut.autorizacion

    @api.multi
    def sri_legalizar_documento(self):
        for r in self:
            # Calculamos la autorización y el tipo de documento.

            # Si existe un comprobante y ese comprobante tiene código
            # NA o no tiene código, significa que el usuario no desea
            # declarar ese documento en sus impuestos.
            if r.comprobante_id and r.comprobante_id.code in ('NA', False):
                return

            aut, tipo = r.set_autorizacion()
            if not aut:
                return

            if aut.tipoem == 'F':
                r.emision_documentos_fisicos(aut, tipo)
            elif aut.tipoem == 'E':
                r.emision_documentos_electronicos(aut, tipo)
            return True

    @api.multi
    def action_date_assign(self):
        """
        Al usar action_date_assign es lo primero en ejecutarse
        en el proceso de validación.
        """
        res = super(AccountInvoice, self).action_date_assign()

        # Generamos los valores de impuestos
        # en todas las facturas.
        self.button_prepare_sri_declaration()

        # Calcularmos los totales si no hay datos
        # en el campo total o no_declarado.
        if not self.total and not self.no_declarado:
            self.compute_sri_invoice_amounts()

        self.sri_legalizar_documento()
        return res

    # Determina el tipo de comprobante de retención emitido en compras.
    r_comprobante_id = fields.Many2one(
        'l10n_ec_sri.comprobante', string='Comprobante retención', domain="[('es_retencion','=', True)]", copy=False, )

    # r_autorizacion_id no se borra, se usa para las autorizaciones propias de retenciones.
    r_autorizacion_id = fields.Many2one(
        'l10n_ec_sri.autorizacion', string=u'Autorización de la retención', copy=False, )
    estabretencion1 = fields.Char(
        'Establecimiento de la retención', copy=False, size=3, )
    ptoemiretencion1 = fields.Char(
        'Punto de emsión de la retención', copy=False, size=3, )
    autretencion1 = fields.Char('Autorización de la retención', copy=False, )
    secretencion1 = fields.Char('Secuencial de la retención', copy=False, )
    fechaemiret1 = fields.Date('Fecha de la retención', copy=False, )

    comprobante_code = fields.Char(
        string='Código de comprobante', related='comprobante_id.code', )
    comprobante_aut = fields.Boolean(
        string='¿Requiere autorización?', related='comprobante_id.requiere_autorizacion', )
    date_invoice = fields.Date(
        string='Invoice Date', readonly=True, states={'draft': [('readonly', False)]}, index=True,
        help="Keep empty to use the current date", copy=False, default=_default_date_invoice, )


    @api.onchange('autorizacion_id')
    def _onchange_autorizacion_id(self):
        self.update({'tipoem': self.autorizacion_id.tipoem,
            'puntoemision': self.autorizacion_id.puntoemision,
            'establecimiento': self.autorizacion_id.establecimiento,
            'autorizacion': self.autorizacion_id.autorizacion})

    @api.onchange('r_autorizacion_id')
    def _onchange_autorizacion_id(self):
        self.update({'ptoemiretencion1': self.r_autorizacion_id.puntoemision,
            'estabretencion1': self.r_autorizacion_id.establecimiento,
            'autretencion1': self.r_autorizacion_id.autorizacion})

    @api.multi
    def button_anular_secuencial(self):
        for inv in self:
            secuencial = inv.secuencial
            autorizacion = inv.autorizacion_id

            if inv.state not in ('draft', 'cancel'):
                inv.secuencial = str(int(secuencial) + 1)
                autorizacion.secuencia_actual = int(secuencial) + 1

            self.env['l10n_ec_sri.comprobantesanulados'].create({
                'fecha': inv.date_invoice,
                'secuencialinicio': secuencial,
                'secuencialfin': secuencial,
                'autorizacion_id': autorizacion.id,
                'comprobante_id': autorizacion.comprobante_id.id,
            })

    # Campos informativos del SRI.
    basenograiva = fields.Monetary(
        string="Subtotal no grava I.V.A.",
        copy=True, )
    baseimponible = fields.Monetary(
        string="Subtotal I.V.A. 0%",
        copy=True, )
    baseimpgrav = fields.Monetary(
        string="Subtotal gravado con I.V.A.",
        copy=True, )
    baseimpexe = fields.Monetary(
        string="Subtotal excento de I.V.A.",
        copy=True, )
    montoiva = fields.Monetary(
        string="Monto I.V.A",
        copy=True, )
    montoice = fields.Monetary(
        string="Monto I.V.A",
        copy=True, )

    # Otros campos informativos de uso interno.
    # No se usa los campos propios de Odoo porque estos restan las retenciones.
    total = fields.Monetary(
        string='TOTAL',
        copy=True, )
    subtotal = fields.Monetary(
        string='SUBTOTAL',
        copy=True, )
    no_declarado = fields.Monetary(
        string='VALOR NO DECLARADO',
        copy=True, )

    # Este campo es necesario para presentarlo en las vistas y usarlo en los reportes
    # que solo discriminan valores con y sin iva, no el detalle requerido por el SRI.
    subtotal_sin_iva = fields.Monetary(
        string="SUBTOTAL SIN IVA", compute="_compute_subtotal_sin_iva", )

    @api.multi
    @api.depends('baseimpexe', 'baseimponible', 'basenograiva')
    def _compute_subtotal_sin_iva(self):
        for r in self:
            r.subtotal_sin_iva = r.baseimpexe + r.baseimponible + r.basenograiva

    @api.multi
    @api.constrains(
        'secuencial', 'comprobante_code',
        'fechaemiret1', 'date_invoice'
    )
    def check_invoice_values(self):
        for inv in self:
            if inv.comprobante_code and inv.secuencial:
                if len(inv.secuencial) > 9:
                    raise UserWarning(
                        _("El número de secuencial debe tener menos de 10 dígitos."))
            if inv.fechaemiret1 and inv.date_invoice > inv.fechaemiret1:
                raise UserWarning(
                    _("La fecha de la retención no puede ser menor que la de la factura."))

    @api.multi
    @api.constrains('secuencial')
    def check_number(self):
        for inv in self:
            if inv.secuencial and not inv.secuencial.isdigit():
                raise UserError(
                    'El secuencial de la factura debe contener solo números')
            if inv.secretencion1 and not inv.secretencion1.isdigit():
                raise UserError(
                    'El secuencial de la retención debe contener solo números')


class AccountInvoiceLine(models.Model):
    _inherit = ['account.invoice.line']

    sri_tax_line_ids = fields.One2many(
        'l10n_ec_sri.tax.line', inverse_name='invoice_line_id', string="Impuestos a declarar", )

    def get_sri_tax_lines_dict(self, line, tax, lt):
        formulario, campo = tax.get_data_from_tag(tax.tag_ids)
        return {
            'invoice_line_id': line.id,
            'formulario': formulario,
            'campo': campo,
            'group': tax.tax_group_id.name,
            'amount': lt['amount'],
            'base': lt['base'],
            'porcentaje': str(abs(int(tax.amount))) or '0',
            'impuesto': tax.impuesto,
            'codigo': tax.codigo,
            'codigoporcentaje': tax.codigoporcentaje,
        }


"""
Modelos adicionales para anexar a la factura en el manejo de impuestos.

Las reglas de nombres se aplican según la siguiente prioridad:
    1.- Se utilizan los nombres de los campos en el ATS o formulario.
    2.- Se utiliza el nombre en las especificaciones de facturación electrónica.
    3.- Si el campo tiene un nombre en Odoo se lo usa, por ejemplo, code o amount.
"""


class SriAtsLine(models.Model):
    _name = 'l10n_ec_sri.ats.line'
    _order = 'codsustento'

    invoice_id = fields.Many2one(
        'account.invoice', ondelete='cascade',
        string="Invoice", required=False, )
    detalleair_ids = fields.One2many(
        'l10n_ec_sri.detalleair', string="Detalle AIR",
        inverse_name='sri_ats_line_id', )
    codsustento = fields.Char('codSustento', )
    basenograiva = fields.Float('baseNoGraIva', digits=(9, 2), )
    baseimponible = fields.Float('baseImponible', digits=(9, 2), )
    baseimpgrav = fields.Float('baseImpGrav', digits=(9, 2), )
    baseimpexe = fields.Float('baseImpExe', digits=(9, 2), )
    montoice = fields.Float('montoIce', digits=(9, 2), )
    montoiva = fields.Float('montoIva', digits=(9, 2), )
    # Retenciones en compras.
    valretbien10 = fields.Float('valRetBien10', digits=(9, 2), )
    valretserv20 = fields.Float('valRetServ20', digits=(9, 2), )
    valretserv50 = fields.Float('valRetServ50', digits=(9, 2), )
    valorretbienes = fields.Float(
        'valorRetBienes', digits=(9, 2), )
    valorretservicios = fields.Float(
        'valorRetServicios', digits=(9, 2), )
    valretserv100 = fields.Float('valRetServ100', digits=(9, 2), )
    # Retenciones en ventas.
    valorretiva = fields.Float('valorRetIva', digits=(9, 2), )
    valorretrenta = fields.Float('valorRetRenta', digits=(9, 2), )


class SriDetalleAir(models.Model):
    _name = 'l10n_ec_sri.detalleair'
    _order = 'codretair'

    sri_ats_line_id = fields.Many2one(
        'l10n_ec_sri.ats.line', ondelete='cascade', string="ATS Line", )
    codretair = fields.Char('codRetAir')
    baseimpair = fields.Float('baseImpAir', digits=(9, 2), )
    porcentajeair = fields.Integer('porcentajeAir')
    valretair = fields.Float('valRetAir', digits=(9, 2), )


class SriTaxLine(models.Model):
    _name = 'l10n_ec_sri.tax.line'
    _order = 'formulario,campo'

    invoice_line_id = fields.Many2one(
        'account.invoice.line', ondelete='cascade', string="Invoice line", )
    invoice_id = fields.Many2one(
        'account.invoice', ondelete='cascade', string="Invoice", )
    formulario = fields.Char('Formulario', )
    campo = fields.Char('Campo', )
    group = fields.Char('Group', )
    amount = fields.Float('Valor del impuesto', digits=(9, 2), )
    porcentaje = fields.Char('Porcentaje', )
    impuesto = fields.Char('Código del impuesto en los formularios', )
    base = fields.Float('Base del impuesto', digits=(9, 2), )
    gap = fields.Float('Diferencia', digits=(9, 2), )

    # Campos para facturacion electronica.
    codigo = fields.Char('Código del impuesto en documentos electrónicos', )
    codigoporcentaje = fields.Char('Código del porcentaje', )
