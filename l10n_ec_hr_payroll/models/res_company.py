# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class res_company(models.Model):
    _inherit = 'res.company'

    basic_wage = fields.Float(_('Basic Wage ($)'), oldname='sueldo_basico')
    iess_representante_legal = fields.Float('Contribución Representante legal IESS (%)', )
    iess_personal = fields.Float('Contribución personal IESS (%)')
    iess_empleador = fields.Float('Contribución patronal IESS (%)')
    porcentaje_fondos_reserva = fields.Float('Fondos de reserva (%)')  # TODO calcular
    default_payroll_journal_id = fields.Many2one(
        'account.journal', string="Default Payroll Journal",
        domain="[('type','=','general')]",
        help="This journal will be used on payroll creation", )
