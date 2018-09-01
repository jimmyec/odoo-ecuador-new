# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
try:
    from stdnum import ec
except ImportError as err:
    _logger.debug('Cannot import stdnum')


class ResPartner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def update_identifiers(self):
        sql = """UPDATE res_partner SET identifier='9999999999'
        WHERE identifier is NULL"""
        self.env.cr.execute(sql)

    @api.model_cr_context
    def init(self):
        self.update_identifiers()
        super(ResPartner, self).init()
        sql_index = """
        CREATE UNIQUE INDEX IF NOT EXISTS
        unique_company_partner_identifier_type on res_partner
        (company_id, type_id, identifier)
        WHERE type_id <> 'pasaporte'"""
        self._cr.execute(sql_index)

    @api.multi
    @api.depends('identifier', 'name')
    def name_get(self):
        data = []
        for partner in self:
            display_val = partner.name
            #display_val = u'{0} {1}'.format(
            #    partner.identifier or '*',
            #    partner.name
            #)
            data.append((partner.id, display_val))
        return data

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        if not args:
            args = []
        if name:
            partners = self.search([('identifier', operator, name)] + args, limit=limit)  # noqa
            if not partners:
                partners = self.search([('name', operator, name)] + args, limit=limit)  # noqa
        else:
            partners = self.search(args, limit=limit)
        return partners.name_get()

    @api.one
    @api.constrains('identifier')
    def _check_identifier(self):
        res = False
        if self.type_id == 'cedula':
            res = ec.ci.is_valid(self.identifier)
        elif self.type_id == 'ruc':
            res = ec.ruc.is_valid(self.identifier)
        else:
            return True
        if not res:
            raise ValidationError('Error en el identificador.')

    @api.one
    @api.depends('identifier')
    def _compute_type_person(self):
        if not self.identifier:
            self.type_person = 'Otro'
        elif int(self.identifier[2]) <= 6:
            self.type_person = 'Natural'
        elif int(self.identifier[2]) in [6, 9]:
            self.type_person = 'Juridica'
        else:
            self.type_person = 'Otro'

    identifier = fields.Char(
            string='Identificación',
            required=True,
            size=13,
            help='Cédula de Identidad, RUC o Pasaporte'
    )
    type_id = fields.Selection(
            string="Documento Id", required=True,
            selection=[
                ('cedula', 'CEDULA'),
                ('ruc', 'RUC'),
                ('pasaporte', 'PASAPORTE')
            ],
            default='pasaporte'
    )
    type_person = fields.Char(
            string='Persona',
            compute='_compute_type_person'
    )
#    is_company = fields.Boolean(default=True)

    def validate_from_sri(self):
        """
        TODO
        """
        SRI_LINK = "https://declaraciones.sri.gob.ec/facturacion-internet/consultas/publico/ruc-datos1.jspa"  # noqa
        texto = '0103893954'  # noqa


class ResCompany(models.Model):
    _inherit = 'res.company'

    namerl = fields.Char(string="Representante Legal", help="Apellidos y Nombres",
            required=True)

    # New fields to the res.company model
    accountant_id = fields.Many2one('res.partner', 'Contador')
    sri_id = fields.Many2one('res.partner', 'SRI')
    cedula_rl = fields.Char('Cédula Rep. Legal', size=10)
    forced_account = fields.Boolean(string="Obligado a llevar contabilidad",
            default=False)
    artesano = fields.Boolean(string="Calificación Artesanal", default=False)
    numart = fields.Char(string="Número")
