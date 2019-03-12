#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class HrSriRetention(models.Model):
    _name = 'hr.sri.retention'
    _description = 'SRI Retention tax table'
    _order = 'name asc'

    def _default_year(self):
        month = fields.datetime.now().strftime("%m")
        year = fields.datetime.now().strftime("%Y")
        if month == '01':
            default = str(int(year) - 1)
        else:
            default = str(year)
        return default

    def _default_name(self):
        month = fields.datetime.now().strftime("%m")
        year = fields.datetime.now().strftime("%Y")
        if month == '01':
            default = str(int(year) - 1)
        else:
            default = str(year)
        name_reference = '%s %s' % (_('Retention Table'), default)
        return name_reference

    name = fields.Char(string=_('Description'), required=True, default=_default_name)
    year = fields.Char(string=_('Year'), default=_default_year, required=True)
    active = fields.Boolean(string=_('Active'), default=True)
    line_ids = fields.One2many('hr.sri.retention.line', 'ret_id', string=_('Details'))
    max_deductible = fields.Float(string=_('Maximum deductible'), default=0.0)
    projection_ids = fields.One2many('hr.sri.projection', 'ret_id', string=_('Projections'))
    old_age = fields.Float(string=_('Exoneration for the elderly'), required=True)
    exoneration_ids = fields.One2many('hr.sri.exoneration.line',
                                      'ret_id', string=_('Exoneration Table'))


class HrSriRetentionLine(models.Model):
    _name = 'hr.sri.retention.line'
    _description = 'SRI Retention tax table details'
    _rec_name = 'basic_fraction'
    _order = 'basic_fraction asc'

    basic_fraction = fields.Float(string=_('Basic Fraction'), required=True, default=0.0)
    excess_up = fields.Float(string=_('Excess Up'), required=True, default=0.0)
    basic_fraction_tax = fields.Integer(string=_('Basic Fraction Tax'), required=True, default=0)
    percent = fields.Integer(string=_('Excess Fraction (%)'), required=True, default=0)
    ret_id = fields.Many2one('hr.sri.retention', string=_(
        'Retention Table'), ondelete='cascade', default=0.0)


class HrSriDeduction(models.Model):
    _name = 'hr.sri.deduction'
    _description = 'Deductions Taxes for Rent'
    _order = 'name asc, code desc'

    code = fields.Char(string=_('Code'), required=True, size=8)
    name = fields.Char(string=_('Name'), required=True, size=32)
    description = fields.Text(_('Description'))


class HrSriProjection(models.Model):
    _name = 'hr.sri.projection'
    _description = 'Maximum value to deduct'
    _order = 'name asc'

    @api.multi
    @api.depends('deduction_id')
    def _compute_name(self):
        for record in self:
            record.name = record.deduction_id.name

    name = fields.Char('Name', compute='_compute_name', )
    deduction_id = fields.Many2one('hr.sri.deduction', string=_('Deduction'), required=True)
    amount = fields.Float(string=_('Maximum Deductible'), required=True)
    ret_id = fields.Many2one('hr.sri.retention', string=_('Retention Table'), ondelete='cascade')


class HrSriExonerationLine(models.Model):
    _name = 'hr.sri.exoneration.line'
    _description = 'Exoneration Table detail for Taxes Rent'
    _order = 'excess_from asc'

    excess_from = fields.Float(string=_('Excess from'), required=True)
    excess_up = fields.Float(string=_('Excess up'), required=True)
    percent = fields.Float(string=_('Exoneration (%)'), required=True)
    ret_id = fields.Many2one('hr.sri.retention', string=_('Retention Table'), ondelete='cascade')


class HrSriAnnualProjection(models.Model):
    _name = 'hr.sri.annual.projection'
    _description = 'Annual Projection'

    def _default_year(self):
        month = fields.datetime.now().strftime("%m")
        year = fields.datetime.now().strftime("%Y")
        if month == '01':
            default = str(int(year) - 1)
        else:
            default = str(year)
        return default

    def _default_name(self):
        month = fields.datetime.now().strftime("%m")
        year = fields.datetime.now().strftime("%Y")
        if month == '01':
            default = str(int(year) - 1)
        else:
            default = str(year)
        name_reference = '{} {}'.format('Proyección de gastos', default)
        return name_reference

    @api.multi
    def _compute_all(self):
        for i in self:
            sum = 0.0
            for line in i.line_ids:
                sum += line.value
            self.total = sum

    name = fields.Char(_('Name'), default=_default_name)
    year = fields.Char(_('Year'), default=_default_year, required=True)
    amount = fields.Float(compute=_compute_all, method=True, string=_('Amount'))
    line_ids = fields.One2many('hr.sri.annual.projection.line',
                               'projection_id', string='Líneas de proyección')
    contract_id = fields.Many2one('hr.contract', string=_('Contract'))


class HrSriAnnualProjectionLine(models.Model):
    _name = 'hr.sri.annual.projection.line'

    name = fields.Char(string=_('Name'), size=8)
    deduction_id = fields.Many2one('hr.sri.deduction', string=_('Deduction'))
    amount = fields.Float(_('Amount'))
    projection_id = fields.Many2one('hr.sri.annual.projection', string=_('Year'))


class HrSriAnnualRentTax(models.Model):
    _name = 'hr.sri.annual.rent.tax'

    name = fields.Char(_('Name'))
    year = fields.Char(_('Year'))
    line_ids = fields.One2many('hr.sri.rent.tax', 'rent_id', string=_('Tax Rent'))
    contract_id = fields.Many2one('hr.contract', string=_('Contract'))


class HrSriRentTax(models.Model):
    _name = 'hr.sri.rent.tax'
    _order = 'year, month asc'

    month = fields.Selection(
        [
            ('01', _('January')),
            ('02', _('February')),
            ('03', _('March')),
            ('04', _('April')),
            ('05', _('May')),
            ('06', _('Jun')),
            ('07', _('July')),
            ('08', _('August')),
            ('09', _('September')),
            ('10', _('October')),
            ('11', _('November')),
            ('12', _('December'))
        ],
        string=_('Month'),
        required=True
    )
    year = fields.Char(_('Year'), size=4, required=True)
    projectable = fields.Float(string=_('Projectable Remuneration(Wage)'))
    non_projectable = fields.Float(string='Non-projectable Remuneration')
    amount = fields.Float(string=_('Income Tax Withheld'))
    rent_id = fields.Many2one('hr.sri.annual.rent.tax', string=_('Annual Rent Tax'))
