# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from stdnum.ec import vat

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.multi
    def _check_age(self):
        for row in self:
            if row.birthday:
                row.old_age = False
                date_birthday = datetime.strptime(row.birthday, "%Y-%m-%d")
                if date_birthday <= datetime.today():
                    today = datetime.today().strftime("%Y-%m-%d")
                    now = today.split('-')
                    birth = row.birthday.split('-')
                    date_now = date(int(now[0]), int(now[1]), int(now[2]))
                    date_birth = date(int(birth[0]), int(birth[1]), int(birth[2]))
                    delta = date_now - date_birth
                    age = delta.days / 365
                    limit = 65 if row.gender == 'male' else 60
                    if age >= limit:
                        row.old_age = True
                    row.age = age

    def split_name(self, name):
        vals = {
            'names': '',
            'lastname': '',
            'second_lastname': ''
        }
        clean_name = name.split(' ')
        if len(clean_name) == 2:
            vals['lastname'] = clean_name[0]
            vals['names'] = clean_name[1]
        elif len(clean_name) > 2:
            vals['lastname'] = clean_name[0]
            vals['second_lastname'] = clean_name[1]
            vals['names'] = " ".join(str(x) for x in clean_name[2:])
        return vals

    @api.model
    def update_employee_names(self):
        employees = self.search([
            ('names', '=', False), ('lastname', '=', False)])
        if employees:
            for ee in employees:
                split_name = self.split_name(ee.name)
                _logger.debug('Split Name for Employees: %s' % ee.name)
                ee.write({
                    'lastname': split_name['lastname'],
                    'second_lastname': split_name['second_lastname'],
                    'names': split_name['names'],
                })
        return True

    @api.onchange('name', 'names', 'lastname', 'second_lastname')
    def onchange_name(self):
        name = ''
        for row in self:
            name = '%s %s %s' % (row.lastname or '', row.second_lastname or '', row.names or '')
            row.name = name

    @api.multi
    @api.depends('family_ids')
    def _get_children(self):
        family_obj = self.env['hr.family']
        for row in self:
            if row.family_ids:
                row.children = family_obj.search_count([
                    ('employee_id', '=', row.id),
                    ('relation', '=', 'child')])

    names = fields.Char(_('Name\'s'), required=True)
    lastname = fields.Char(_('Lastname'), required=True)
    second_lastname = fields.Char(_('Second Lastname'))
    flag = fields.Boolean(_('Job Change'))
    age = fields.Integer(compute=_check_age, string=_('Age'))
    old_age = fields.Boolean(
        compute=_check_age, string=("Old Age"),
        store=False, oldname='tercera_edad'
    )
    department_id = fields.Many2one('hr.department', string=_(
        'Department'), related='job_id.department_id', readonly=True)
    parent_id = fields.Many2one('hr.employee', string=_(
        'Manager'), related='department_id.manager_id', readonly=True)
    disability = fields.Boolean(_('Disability'))
    conadis_id = fields.Char(_('CONADIS No'))
    disability_type = fields.Char(_('Disability Type'))
    disability_percent = fields.Float(_('Disability Percent'))
    family_ids = fields.One2many('hr.family', 'employee_id', string=_('Family'))
    children = fields.Integer(compute=_get_children, string="Children", store=True)
    marital = fields.Selection(selection_add=[('union_fact', _('Union of Fact'))])

    @api.constrains('identification_id', 'passport_id')
    def _check_identification_number(self):
        for row in self:
            if row.identification_id is False and row.passport_id is False:
                raise ValidationError(
                    _('The employee must have an identification number or passport number'))

            identification_ids = [i.id for i in self.search([('identification_id', '=', row.identification_id),
                                                             ('identification_id', '!=', False)])]
            if identification_ids and row.id not in identification_ids:
                raise ValidationError(_('The identification number must be unique per employee'))
            passport_ids = [i.id for i in self.search([('passport_id', '=', row.passport_id),
                                                       ('passport_id', '!=', False)])]
            if passport_ids and row.id not in passport_ids:
                raise ValidationError(_('The identification number must be unique per employee'))
            if row.identification_id and not vat.ci.is_valid(row.identification_id):
                raise ValidationError(_('The identification number is wrong'))

    @api.model
    def create(self, vals):
        if vals.get('job_id'):
            vals['flag'] = True
        return super(HrEmployee, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('job_id'):
            vals['flag'] = True
        return super(HrEmployee, self).write(vals)
