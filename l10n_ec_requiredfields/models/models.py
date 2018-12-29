# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
try:
    from stdnum import ec
except ImportError as err:
    _logger.debug('Cannot import stdnum')

class requiredfieldsCompany(models.Model):
    _inherit = 'res.company'

    # New fields to the res.company model
    ruc = fields.Char(string="RUC", size=13, required=True)
    namerl = fields.Char(string="Nombre", help="Apellidos y Nombres. Razón Social",
            required=True)
    ollc = fields.Boolean(string="Obligado a llevar contabilidad",
            default=False)
    artesano = fields.Boolean(string="Calificación Artesanal", default=False)
    numart = fields.Char(string="Número")

class requiredfieldsPartner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def update_identifiers(self):
        sql = """UPDATE res_partner SET identifier='9999999999'
        WHERE identifier is NULL"""
        self.env.cr.execute(sql)

    @api.one
    @api.depends('identifier')
    def _kindperson(self):
        if not self.identifier:
            self.kind_p = 'Otro'
        elif int(self.identifier[2]) <= 6:
            self.kind_p = 'Natural'
        elif int(self.identifier[2]) in [6, 9]:
            self.kind_p = 'Juridica'
        else:
            self.kind_p = 'Otro'

    @api.one
    @api.constrains('identifier')
    def _check_identifier(self):
        res = False
        if self.kind_i == 'cedula':
            res = ec.ci.is_valid(self.identifier)
        elif self.kind_i == 'ruc':
            res = ec.ruc.is_valid(self.identifier)
        else:
            return True
        if not res:
            raise ValidationError('Error en el identificador.')

    # New fields to the res.partner model
    identifier = fields.Char(string="Identificación",
                             required=True,
                             size=13,
                             help='Cédula de Identidad, RUC o Pasaporte')

    kind_i = fields.Selection(string="Documento Id", required=True,
        selection=[
            ('cedula','Cédula'),
            ('ruc','RUC'),
            ('pasaporte','Pasaporte'),
            ('venta_consumidor_final','CF')
        ], default='venta_consumidor_final')

    kind_p = fields.Char(string="Persona", compute='_kindperson')
