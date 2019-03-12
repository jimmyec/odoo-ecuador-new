# -*- coding: utf-8 -*-

from odoo import _, fields, models


class HrDepartment(models.Model):
    """
    This module adds the accounting information for each salary item,
    depending on the department assigned to the employee
    """
    _inherit = 'hr.department'

    salaryrule_map_ids = fields.One2many('hr.department.salaryrule.map',
                                         'department_id',
                                         string=_('Salary Rules'))


class HrDepartmentSalaryrulMap(models.Model):
    """
    This module contains the accounting detail of the salary rules
    by department
    """
    _name = 'hr.department.salaryrule.map'
    _description = __doc__

    department_id = fields.Many2one('hr.department',
                                    string=_('Department'))
    rule_id = fields.Many2one('hr.salary.rule',
                              string=_('Salary Rule'),
                              required=True)
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string=_('Analytic Account'),
                                          domain=[('account_type', '=', 'normal')])
    account_tax_id = fields.Many2one('account.tax', string=_('Tax'))
    account_debit = fields.Many2one('account.account',
                                    string=_('Debit Account'),
                                    domain=[('deprecated', '=', False)])
    account_credit = fields.Many2one('account.account',
                                     string=_('Credit Account'),
                                     domain=[('deprecated', '=', False)])
