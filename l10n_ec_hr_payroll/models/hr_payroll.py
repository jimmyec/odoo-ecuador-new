# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class HrPayslipRun(models.Model):
    _inherit = ['hr.payslip.run']

    def _get_default_journal(self):
        res = self.env.user.company_id.default_payroll_journal_id
        if res:
            return res
        return False

    journal_id = fields.Many2one(default=_get_default_journal, )


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_default_journal(self):
        res = self.env.user.company_id.default_payroll_journal_id
        if res:
            return res
        return False

    journal_id = fields.Many2one(default=_get_default_journal, )

    def get_worked_day_lines(self, cr, uid, contract_ids, date_from, date_to, context=None):
        """
        @param contract_ids: list of contract id
        @return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to
        """
        def verificar_ausencia_contrato(contrato, dia):
            resultado = True
            if contrato.date_start:
                dia_inicio = datetime.strptime(contrato.date_start, "%Y-%m-%d")
                if dia >= dia_inicio:
                    if contrato.date_end:
                        dia_fin = datetime.strptime(contrato.date_end, "%Y-%m-%d")
                        if dia <= dia_fin:
                            resultado = False
                    else:
                        resultado = False
            return resultado

        def was_on_leave(employee_id, datetime_day, context=None):
            res = {}
            day = datetime_day.strftime("%Y-%m-%d")
            holiday_ids = self.pool.get('hr.holidays').search(cr, uid, [
                ('state', '=', 'validate'),
                ('employee_id', '=', employee_id),
                ('type', '=', 'remove'),
                ('date_from', '<=', day),
                ('date_to', '>=', day)])
            if holiday_ids:
                res['data'] = self.pool.get('hr.holidays').browse(
                    cr, uid, holiday_ids, context=context)[0]
                res['type'] = 'ausent'
            return res

        res = []
        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': 0.0,
                'number_of_hours': 0.0,
                'contract_id': contract.id,
            }
            leaves = {}
            day_from = datetime.strptime(date_from, "%Y-%m-%d")
            day_to = datetime.strptime(date_to, "%Y-%m-%d")

            # FIXME Código tomado de hr_holidays para determinar el número de días del mes.
            # Reescribir el código para buscar una forma más adecuada de hacer este cálculo.
            DATETIME_FORMAT = "%Y-%m-%d"
            from_dt = datetime.strptime(date_from, DATETIME_FORMAT)
            to_dt = datetime.strptime(date_to, DATETIME_FORMAT)
            range_len = to_dt - from_dt
            nb_of_days = (range_len.days + float(range_len.seconds) / 86400) + 1
            for day in range(0, int(nb_of_days)):
                leave_type = was_on_leave(contract.employee_id.id, day_from +
                                          timedelta(days=day), context=context)
                leave_contract = verificar_ausencia_contrato(
                    contract, day_from + timedelta(days=day))

                """ El número de días trabajados siempre es 30, indistintamente del número real de días
                    en el mes. ¿Debemos permitir que el número de días pueda ser variable? """
                attendances['number_of_days'] = 30
                if leave_type:
                    # the employee had to work
                    if leave_type['data'] in leaves:
                        leaves[leave_type['data']]['number_of_days'] += 1.0
                    elif leave_type['type'] == 'ausent':
                        leaves[leave_type['data']] = {
                            'name': leave_type['data'].holiday_status_id.name,
                            'sequence': 5,
                            'code': leave_type['data'].holiday_status_id.code or '',
                            'number_of_days': 1.0,
                            'contract_id': contract.id,
                        }
            leaves = [value for key, value in leaves.items()]
            res += [attendances] + leaves
        return res

    def get_payslip_lines(self, cr, uid, contract_ids, payslip_id, context):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict[
                'categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):

            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(amount) as sum\
                            FROM hr_payslip as hp, hr_payslip_input as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()[0]
                return res or 0.0

        class sri(BrowsableObject):

            def tax_rent(self, contract, date_from, projectable, non_projectable, iess_percent):
                rent_tax_obj = self.pool.get('hr.sri.rent.tax')
                annual_tax_obj = self.pool.get('hr.sri.annual.rent.tax')
                amount = annual_amount = 0.0
                month = str(date_from)[5:7]
                year = str(date_from)[0:4]
                previous = previous_np = contribuited = 0
                annual_id = None
                if contract.rent_tax_ids:
                    for row in contract.rent_tax_ids:
                        if row.year == year:
                            annual_id = row.id
                            if row.line_ids:
                                for line in row.line_ids:
                                    if line.month == month:
                                        rent_tax_obj.unlink(self.cr, self.uid, line.id)
                    for row in contract.rent_tax_ids:
                        if row.year == year:
                            for line in row.line_ids:
                                if line.month != month and line.month < month:
                                    previous += line.projectable
                                    previous_np += line.non_projectable
                                    contribuited += line.amount
                else:
                    annual_id = annual_tax_obj.create(self.cr, self.uid, {
                        'name': 'Rent Tax %s' % year,
                        'year': year,
                        'contract_id': contract.id
                    })
                previous_iess = previous * iess_percent
                previous_np_iess = previous_np * iess_percent
                base = (projectable * (13 - int(month))) + non_projectable + previous + previous_np
                iess = ((projectable * (13 - int(month))) * iess_percent)
                base -= (iess + previous_iess + previous_np_iess)

                deductible = 0
                if contract.projection_ids:
                    for row in contract.projection_ids:
                        if row.year == year:
                            for line in row.line_ids:
                                deductible += line.amount

                table_obj = self.pool.get('hr.sri.retention')
                line_obj = self.pool.get('hr.sri.retention.line')

                table_ids = table_obj.search(self.cr, self.uid, [('year', '=', year),
                                                                 ('active', '=', True)])
                if table_ids:
                    for row in table_obj.browse(self.cr, self.uid, table_ids):
                        if row.max_deductible < deductible and row.max_deductible > 0:
                            deductible = row.max_deductible
                        base = base - deductible
                        line_ids = line_obj.search(self.cr, self.uid, [('ret_id', '=', row.id),
                                                                       ('basic_fraction', '<=', base),
                                                                       ('excess_up', '>=', base)])
                        for line in line_obj.browse(self.cr, self.uid, line_ids):
                            annual_amount += line.basic_fraction_tax
                            annual_amount += (((base - line.basic_fraction) * line.percent) / 100)
                            amount = (annual_amount - contribuited) / (13 - int(month))
                            rent_tax_obj.create(self.cr, self.uid, {'year': year,
                                                                    'month': month,
                                                                    'projectable': projectable,
                                                                    'non_projectable': non_projectable,
                                                                    'amount': amount,
                                                                    'rent_id': annual_id})
                if amount > 0:
                    return amount
                return 0

        class WorkedDays(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                result = 0.0
                self.cr.execute("SELECT sum(number_of_days) as number_of_days, sum(number_of_hours) as number_of_hours\
                            FROM hr_payslip as hp, hr_payslip_worked_days as pi \
                            WHERE hp.employee_id = %s AND hp.state = 'done'\
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s",
                                (self.employee_id, from_date, to_date, code))
                return self.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """a class that will be used into the python code, mainly for usability purposes"""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = datetime.now().strftime('%Y-%m-%d')
                self.cr.execute("SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)\
                            FROM hr_payslip as hp, hr_payslip_line as pl \
                            WHERE hp.employee_id = %s AND hp.state = 'done' \
                            AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s",
                                (self.employee_id, from_date, to_date, code))
                res = self.cr.fetchone()
                return res and res[0] or 0.0

        # we keep a dict with the result because a value can be overwritten by
        # another rule with the same code
        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        payslip_obj = self.pool.get('hr.payslip')
        inputs_obj = self.pool.get('hr.payslip.worked_days')
        obj_rule = self.pool.get('hr.salary.rule')
        payslip = payslip_obj.browse(cr, uid, payslip_id, context=context)
        worked_days = {}
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days[worked_days_line.code] = worked_days_line
        inputs = {}
        inputs_vals = {}
        for input_line in payslip.input_line_ids:
            inputs[input_line.code] = input_line
            if input_line.code in inputs_vals:
                inputs_vals[input_line.code]['amount'] += input_line.amount
            else:
                inputs_vals[input_line.code] = {'amount': input_line.amount}

        categories_obj = BrowsableObject(
            self.pool, cr, uid, payslip.employee_id.id, categories_dict)
        input_obj = InputLine(self.pool, cr, uid, payslip.employee_id.id, inputs)
        worked_days_obj = WorkedDays(
            self.pool, cr, uid, payslip.employee_id.id, worked_days)
        payslip_obj = Payslips(self.pool, cr, uid, payslip.employee_id.id, payslip)
        rules_obj = BrowsableObject(self.pool, cr, uid, payslip.employee_id.id, rules)

        sri_obj = sri(self.pool, cr, uid, payslip.employee_id.id, payslip_obj)
        baselocaldict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': payslip_obj,
                         'worked_days': worked_days_obj, 'inputs': input_obj, 'sri': sri_obj}
        # get the ids of the structures on the contracts and their parent id as well
        structure_ids = self.pool.get('hr.contract').get_all_structures(
            cr, uid, contract_ids, context=context)
        # get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(
            cr, uid, structure_ids, context=context)
        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

        for contract in self.pool.get('hr.contract').browse(cr, uid, contract_ids, context=context):
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if obj_rule.satisfy_condition(cr, uid, rule.id, localdict, context=context) and rule.id not in blacklist:
                    # compute the amount of the rule
                    amount, qty, rate = obj_rule.compute_rule(
                        cr, uid, rule.id, localdict, context=context)
                    # sum inputs amount
                    if rule.code in inputs_vals:
                        amount = inputs_vals[rule.code]['amount']
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(
                        localdict, rule.category_id, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in self.pool.get(
                        'hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]

        result = [value for code, value in result_dict.items()]
        return result

    @api.multi
    def process_sheet(self):
        move_pool = self.env['account.move']
        precision = self.env['decimal.precision'].precision_get('Payroll')
        rule_map_obj = self.env['hr.department.salaryrule.map']

        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to

            name = _('Payslip of %s') % (slip.employee_id.name)
            move = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }
            for line in slip.details_by_salary_rule_category:
                amt = slip.credit_note and -line.total or line.total
                if float_is_zero(amt, precision_digits=precision):
                    continue
                debit_account_id = line.salary_rule_id.account_debit.id
                credit_account_id = line.salary_rule_id.account_credit.id
                analytic_account_id = line.salary_rule_id.analytic_account_id and line.salary_rule_id.analytic_account_id.id or False
                tax_line_id = line.salary_rule_id.account_tax_id and line.salary_rule_id.account_tax_id.id or False
                if slip.contract_id.department_id:
                    map_id = rule_map_obj.search(
                        [('department_id', '=', line.employee_id.department_id.id),
                         ('rule_id', '=', line.salary_rule_id.id)])
                    if map_id:
                        debit_account_id = map_id.account_debit and map_id.account_debit.id
                        credit_account_id = map_id.account_credit and map_id.account_credit.id
                        analytic_account_id = map_id.analytic_account_id and map_id.analityc_account_id.id
                        tax_line_id = map_id.account_tax_id and map_id.account_tax_id.id

                if debit_account_id:
                    debit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(line, credit_account=False),
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amt > 0.0 and amt or 0.0,
                        'credit': amt < 0.0 and -amt or 0.0,
                        'analytic_account_id': analytic_account_id,
                        'tax_line_id': tax_line_id
                    })
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

                if credit_account_id:
                    credit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(line, credit_account=True),
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amt < 0.0 and -amt or 0.0,
                        'credit': amt > 0.0 and amt or 0.0,
                        'analytic_account_id': analytic_account_id,
                        'tax_line_id': tax_line_id
                    })
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (
                        slip.journal_id.name))
                adjust_credit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': 0.0,
                    'credit': debit_sum - credit_sum,
                })
                line_ids.append(adjust_credit)

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                acc_id = slip.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (
                        slip.journal_id.name))
                adjust_debit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': credit_sum - debit_sum,
                    'credit': 0.0,
                })
                line_ids.append(adjust_debit)

            move['line_ids'] = line_ids
            move_id = move_pool.create(move)
            move_id.post()
        return self.write({
            'paid': True,
            'state': 'done',
            'move_id': move_id.id,
            'date': date
        })
