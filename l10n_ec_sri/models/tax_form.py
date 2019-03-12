# -*- coding: utf-8 -*-
import base64
import logging
from collections import OrderedDict
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import xmltodict
except ImportError:
    _logger.error(
        "The module xmltodict can't be loaded, try: pip install xmltodict")


class SriTaxFormSet(models.Model):
    _name = 'l10n_ec_sri.tax.form.set'
    _order = 'date_from'

    @api.multi
    def prepare_sri_declaration(self):
        for s in self:
            invoices = s.in_invoice_ids + s.in_refund_ids + \
                s.out_invoice_ids + s.out_refund_ids
            for inv in invoices:
                inv.button_prepare_sri_declaration()

    @api.multi
    def get_invoices(self):
        for s in self:
            # Obtenemos todas las facturas abiertas y pagadas del periodo.
            invoices = self.env['account.invoice'].search([
                ('state', 'in', ('open', 'paid')),
                ('date_invoice', ">=", self.date_from),
                ('date_invoice', '<=', self.date_to),
            ])
            no_declarado = invoices.filtered(
                lambda x: x.comprobante_id.code in ('NA', False))
            invoices -= no_declarado

            out_invoice = invoices.filtered(lambda x: x.type == 'out_invoice')

            # Agregamos las devoluciones en venta sin valor a las ventas
            # puesto que así se ingresan las retenciones de tarjeta de crédito.
            out_invoice += invoices.filtered(lambda x: x.subtotal ==
                                             0 and x.type == 'out_refund')

            # Restamos las facturas ya procesadas para mejorar el rendimiento.
            invoices -= out_invoice

            in_invoice = invoices.filtered(lambda x: x.type == 'in_invoice')
            invoices -= in_invoice

            # No restamos lo procesado porque la lista es pequeña.
            in_refund = invoices.filtered(lambda x: x.type == 'in_refund')
            out_refund = invoices.filtered(lambda x: x.type == 'out_refund')

            s.update({
                'no_declarado_ids': no_declarado,
                'out_invoice_ids': out_invoice,
                'out_refund_ids': out_refund,
                'in_invoice_ids': in_invoice,
                'in_refund_ids': in_refund,
            })

    date_from = fields.Date('Desde', required=True, )
    date_to = fields.Date('Hasta', required=True, )

    sri_tax_form_ids = fields.One2many(
        'l10n_ec_sri.tax.form', inverse_name='sri_tax_form_set_id',
        string='Tax declarations', )

    no_declarado_ids = fields.Many2many(
        'account.invoice', 'no_declarado_tax_form_set_rel', 'no_declarado_ids',
        'no_declarado_tax_form_set_ids', string="Comprobantes no declarados", )
    in_invoice_ids = fields.Many2many(
        'account.invoice', 'in_inv_tax_form_set_rel', 'in_invoice_ids',
        'in_inv_tax_form_set_ids', string="In invoices", )
    out_invoice_ids = fields.Many2many(
        'account.invoice', 'out_inv_tax_form_set_rel', 'out_invoice_ids',
        'out_inv_tax_form_set_ids', string="Out invoices", )
    in_refund_ids = fields.Many2many(
        'account.invoice', 'in_ref_tax_form_set_rel', 'in_refund_ids',
        'in_ref_tax_form_set_ids', string="In refunds", )
    out_refund_ids = fields.Many2many(
        'account.invoice', 'out_ref_tax_form_set_rel', 'out_refund_ids',
        'out_ref_tax_form_set_ids', string="Out refunds", )
    in_reembolso_ids = fields.One2many(
        'account.invoice', string='Reembolsos en compras',
        compute='_compute_reembolsos', readonly=True, )

    @api.multi
    @api.depends('in_invoice_ids', 'out_invoice_ids')
    def _compute_reembolsos(self):
        for f in self:
            f.in_reembolso_ids = f.in_invoice_ids.mapped("reembolso_ids")


class SriTaxForm(models.Model):
    _name = 'l10n_ec_sri.tax.form'
    _order = 'formulario'

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Presentado'),
        ('replaced', 'Sustituido'),
    ],
        string='Estado',
        default='draft', )

    formulario = fields.Selection([
        ('101', '101'),
        ('103', '103'),
        ('104', '104'),
        ('ats', 'Anexo Transaccional'),
    ])
    sri_tax_form_set_id = fields.Many2one(
        'l10n_ec_sri.tax.form.set', ondelete='cascade',
        string="Tax Form Set", )
    date_from = fields.Date(
        'Desde', related='sri_tax_form_set_id.date_from', )
    date_to = fields.Date(
        'Hasta', related='sri_tax_form_set_id.date_to', )

    sri_tax_form_line_ids = fields.One2many(
        'l10n_ec_sri.tax.form.line',
        inverse_name='sri_tax_form_id',
        string='Tax declarations', )

    payment_ids = fields.Many2many(
        'account.payment', 'payment_tax_form_rel', 'payment_ids',
        'tax_form_ids', string="Payments", )

    move_ids = fields.Many2many(
        'account.move', 'move_tax_form_rel', 'move_ids',
        'tax_form_ids', string="Move", )

    xml_file = fields.Binary('Archivo XML', attachment=True, readonly=True, )
    xml_filename = fields.Char(string="Archivo XML")

    declarar_facturas_electronicas = fields.Boolean(
        string='Declarar facturas electronicas', default=True, )

    @api.multi
    def prepare_ats(self):
        """
        Método para ser heredado.
        :return: dict con valores del ATS
        """
        for f in self:
            inv = self.env['account.invoice']
            form_set = f.sri_tax_form_set_id

            # Para generar los datos de ventas
            ventas = form_set.out_invoice_ids
            if not f.declarar_facturas_electronicas:
                ventas = ventas.filtered(lambda x: x.tipoem == 'F')

            devoluciones = form_set.out_refund_ids
            if not f.declarar_facturas_electronicas:
                devoluciones = devoluciones.filtered(lambda x: x.tipoem == 'F')

            detalleVentas = []
            establecimientos = set(
                (ventas + devoluciones).mapped('establecimiento'))
            establecimientos = establecimientos - set(['999', False])
            ventaEst = []
            for e in establecimientos:
                e_ventas = sum(ventas.filtered(
                    lambda r: r.establecimiento == e).mapped('subtotal')) or 0.00
                e_devoluciones = sum(devoluciones.filtered(
                    lambda r: r.establecimiento == e).mapped('subtotal')) or 0.00

                ventaEst.append(OrderedDict([
                    ('codEstab', e),
                    ('ventasEstab', '{:.2f}'.format(
                        e_ventas - e_devoluciones)),
                    ('ivaComp', '{:.2f}'.format(0)),  # TODO: ¿es necesario?
                ]))

            totalVentas = sum(float(v['ventasEstab']) for v in ventaEst)
            numEstabRuc = str(len(ventaEst)).zfill(3)

            partners = (ventas + devoluciones).mapped('partner_id')

            # Necesitamos una segunda lista de partners para comparar los ya procesados.
            pending_partners = partners

            for p in partners:
                # Continuamos si el partner ya ha sido procesado.
                if p not in pending_partners:
                    continue

                # Filtramos los partners por cédula y RUC
                vat = p.vat
                if len(vat) == 13:
                    id_fiscal = [vat, vat[:9]]
                elif len(vat) == 10:
                    id_fiscal = [vat, vat + '001']
                else:
                    id_fiscal = [vat]

                contribuyentes = partners.filtered(lambda r: r.vat in id_fiscal)
                # Restamos los partners para evitar duplicar el cálculo.
                pending_partners -= contribuyentes

                p_ventas = ventas.filtered(lambda r: r.partner_id in contribuyentes)
                p_devoluciones = devoluciones.filtered(
                    lambda r: r.partner_id in contribuyentes)

                t_ventas = p_ventas.mapped('sri_ats_line_ids')
                t_devoluciones = p_devoluciones.mapped('sri_ats_line_ids')

                # Restamos de ventas y devoluciones para incrementar eficiencia.
                ventas -= p_ventas
                devoluciones -= p_devoluciones

                fiscal = p.property_account_position_id
                identificacion = fiscal.identificacion_id

                fp_inv = p_ventas.filtered(lambda inv: inv.subtotal >= 1000)

                formaPago = []
                if fp_inv:
                    formaPago = list(
                        set(fp_inv.mapped('payment_ids').mapped('formapago_id.code')))
                if not formaPago:
                    formaPago.append(p.formapago_id.code or '01')

                tpidcliente = identificacion.tpidcliente
                vals = OrderedDict([
                    ('tpIdCliente', tpidcliente),
                    ('idCliente', p.vat),
                    ('parteRelVtas', p.parterel and 'SI' or 'NO')
                ])

                if tpidcliente == '06':
                    vals.update(OrderedDict([
                        ('tipoCliente', fiscal.persona_id.tpidprov),
                        # Al declarar el ATS sale un error que indica que se debe
                        # declarar DenoCli cuando el tipo es 06.
                        # ('DenoCli', inv.normalize_text(p.name))
                    ]))

                # Bases de impuesto para determinar si el balance es positivo o negativo.
                basenograiva = sum(t_ventas.mapped('basenograiva')) - sum(
                    t_devoluciones.mapped('basenograiva')) or 0.00
                baseimponible = sum(t_ventas.mapped('baseimponible')) - sum(
                    t_devoluciones.mapped('baseimponible'))
                baseimpgrav = sum(t_ventas.mapped('baseimpgrav')) - sum(
                    t_devoluciones.mapped('baseimpgrav'))
                balance = basenograiva + baseimponible + baseimpgrav

                tipoComprobante = '18'
                if balance < 0:
                    tipoComprobante = '04'

                montoiva = sum(t_ventas.mapped('montoiva')) - sum(
                    t_devoluciones.mapped('montoiva')) or 0.00
                montoice = sum(t_ventas.mapped('montoice')) - sum(
                    t_devoluciones.mapped('montoice')) or 0.00
                valorretiva = sum(t_ventas.mapped('valorretiva')) - sum(
                    t_devoluciones.mapped('valorretiva')) or 0.00
                valorretrenta = sum(t_ventas.mapped('valorretrenta')) - sum(
                    t_devoluciones.mapped('valorretrenta')) or 0.00

                vals.update(OrderedDict([
                    # En ventas siempre usamos 18 para las ventas y
                    # 04 para las notas de crédito.
                    ('tipoComprobante', tipoComprobante),
                    # Las facturas electrónicas no se declaran.
                    ('tipoEmision', 'F'),
                    ('numeroComprobantes', len(p_ventas) + len(p_devoluciones)),
                    ('baseNoGraIva', '{:.2f}'.format(abs(basenograiva))),
                    ('baseImponible', '{:.2f}'.format(abs(baseimponible))),
                    ('baseImpGrav', '{:.2f}'.format(abs(baseimpgrav))),
                    ('montoIva', '{:.2f}'.format(abs(montoiva))),
                    # TODO: Tipo y monto de compensaciones, por desarrollar.
                    # ('tipoCompe', ''),
                    # ('monto', '{:.2f}'.format(0)),
                    ('montoIce', '{:.2f}'.format(abs(montoice))),
                    ('valorRetIva', '{:.2f}'.format(abs(valorretiva))),
                    ('valorRetRenta', '{:.2f}'.format(abs(valorretrenta))),
                ]))

                # Solo se declaran formasDePago en comprobantes de venta '18'
                if formaPago and tipoComprobante == '18':
                    vals.update([
                        ('formasDePago', {'formaPago': formaPago})
                    ])

                detalleVentas.append(vals)

            ventas = OrderedDict([
                ('detalleVentas', detalleVentas),
            ])

            ventasEstablecimiento = OrderedDict([
                ('ventaEst', ventaEst),
            ])

            # Para la información general del informante
            date = f.sri_tax_form_set_id.date_to
            company = self.env.user.company_id
            informante = company.partner_id
            fiscal = informante.property_account_position_id
            iva = OrderedDict([
                ('TipoIDInformante', fiscal.identificacion_id.code),
                ('IdInformante', informante.vat),
                ('razonSocial', inv.normalize_text(informante.name)),
                ('Anio', datetime.strptime(date, '%Y-%m-%d').strftime('%Y')),
                ('Mes', datetime.strptime(date, '%Y-%m-%d').strftime('%m'))
            ])

            if numEstabRuc != '000':
                iva.update(OrderedDict([
                    ('numEstabRuc', numEstabRuc)
                ]))

            if totalVentas != 0:
                iva.update(OrderedDict([
                    ('totalVentas', '{:.2f}'.format(totalVentas))
                ]))

            iva.update(OrderedDict([
                ('codigoOperativo', 'IVA')
            ]))

            # Diccionario de compras
            compras = form_set.in_invoice_ids + form_set.in_refund_ids

            detalleCompras = OrderedDict([('detalleCompras', [])])

            for c in compras:
                detalleCompra = c.prepare_detallecompras_dict()
                for dc in detalleCompra:
                    detalleCompras['detalleCompras'].append(dc)

            res = {
                'iva': iva,
                'ventas': ventas,
                'ventasEstablecimiento': ventasEstablecimiento,
                'compras': detalleCompras
            }
            return res

    @api.multi
    def get_ats_xml(self):
        decl = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>"""
        for f in self:
            vals = f.prepare_ats()
            data = OrderedDict([
                ('iva', vals['iva']),
            ])

            data['iva'].update([
                ('compras', vals['compras'])
            ])

            if vals['ventas']['detalleVentas']:
                data['iva'].update([
                    ('ventas', vals['ventas'])
                ])

            if vals['ventasEstablecimiento']['ventaEst']:
                data['iva'].update([
                    ('ventasEstablecimiento', vals['ventasEstablecimiento'])
                ])

            xml_data = decl + \
                xmltodict.unparse(data, pretty=True, full_document=False)
            f.write({'xml_filename': 'ATS.xml',
                     'xml_file': base64.encodestring(xml_data)})

    @api.multi
    def get_tax_form_lines(self):
        for f in self:
            # Limpiamos las líneas de impuestos previamente creadas.
            f.sri_tax_form_line_ids.unlink()

            tax_form_lines = []

            # Calculamos los impuestos en ventas.
            in_ref = f.sri_tax_form_set_id.mapped('in_refund_ids')
            in_inv = f.sri_tax_form_set_id.mapped('in_invoice_ids')
            purchases = in_inv + in_ref

            taxes = purchases.mapped('sri_tax_line_ids').filtered(
                lambda r: r.formulario == f.formulario)

            for t in set(taxes.mapped('campo')):
                facturas = in_inv.mapped('sri_tax_line_ids').filtered(
                    lambda r: r.campo == t)
                devoluciones = in_ref.mapped(
                    'sri_tax_line_ids').filtered(lambda r: r.campo == t)

                bruto = sum(facturas.mapped('base'))
                neto = bruto - sum(devoluciones.mapped('base'))
                impuesto = sum(facturas.mapped('amount')) - \
                    sum(devoluciones.mapped('amount'))

                tax_form_lines.append({
                    'sri_tax_form_id': f.id,
                    'campo': t,
                    'bruto': bruto,
                    'neto': neto,
                    'impuesto': impuesto,
                })

            # Calculamos los impuestos en compras.
            out_inv = f.sri_tax_form_set_id.mapped('out_invoice_ids')
            out_ref = f.sri_tax_form_set_id.mapped('out_refund_ids')
            sale_inv = out_inv + out_ref

            taxes = sale_inv.mapped('sri_tax_line_ids').filtered(
                lambda r: r.formulario == f.formulario)

            for t in set(taxes.mapped('campo')):
                facturas = out_inv.mapped('sri_tax_line_ids').filtered(
                    lambda r: r.campo == t)
                devoluciones = out_ref.mapped(
                    'sri_tax_line_ids').filtered(lambda r: r.campo == t)

                bruto = sum(facturas.mapped('base'))
                neto = bruto - sum(devoluciones.mapped('base'))
                impuesto = sum(facturas.mapped('amount')) - \
                    sum(devoluciones.mapped('amount'))

                tax_form_lines.append({
                    'sri_tax_form_id': f.id,
                    'campo': t,
                    'bruto': bruto,
                    'neto': neto,
                    'impuesto': impuesto,
                })

            for line in tax_form_lines:
                self.env['l10n_ec_sri.tax.form.line'].create(line)


class SriTaxFormLine(models.Model):
    _name = 'l10n_ec_sri.tax.form.line'
    _order = 'campo'

    @api.multi
    def _compute_tax_lines(self):
        for r in self:
            s = r.sri_tax_form_id.sri_tax_form_set_id
            invoices = s.in_invoice_ids + s.in_refund_ids + \
                s.out_invoice_ids + s.out_refund_ids
            taxes = invoices.mapped('sri_tax_line_ids')
            r.sri_tax_line_ids = taxes.filtered(lambda x: x.campo == r.campo)

    sri_tax_line_ids = fields.One2many(
        'l10n_ec_sri.tax.line', compute=_compute_tax_lines,
        string='Tax lines', )

    sri_tax_form_id = fields.Many2one(
        'l10n_ec_sri.tax.form', ondelete='cascade',
        string="Tax form", )
    description = fields.Char('Nombre')
    campo = fields.Char('Campo')
    bruto = fields.Float('Valor bruto', digits=(9, 2), )
    neto = fields.Float('Valor neto', digits=(9, 2), )
    impuesto = fields.Float('Impuesto', digits=(9, 2), )
