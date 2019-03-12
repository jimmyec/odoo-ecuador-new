# -*- coding: utf-8 -*-
from odoo import fields, models


class HrHolidaysStatus(models.Model):
    _inherit = ['hr.holidays.status']

    code = fields.Char(
        'Code', help="This code should match the code on the payslip "
                     "rule used to compute the values on the payroll", )
