# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError


class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.onchange('basic_wage')
    def _onchange_basic_wage(self):
        if self.basic_wage is True:
            self.wage = self.env.user.company_id.basic_wage
        else:
            self.wage = 0.0

    @api.onchange('representante_legal')
    def _onchange_representante_legal(self):
        if not self.representante_legal:
            self.iess_representante_legal = False

    flag = fields.Boolean(_('Contract Change'))
    active = fields.Boolean(_('Active Contract'), default=True)
    department_id = fields.Many2one('hr.department', string=_(
        'Department'), related='employee_id.department_id', readonly=True)
    job_id = fields.Many2one('hr.job', string=_(
        'Job Title'), related='employee_id.job_id', readonly=True)
    representante_legal = fields.Boolean('Es representante legal', )
    iess_representante_legal = fields.Boolean(
        '¿IESS de representánte legal?',
        help="Aplica la regla salarial del IESS, vigente desde enero de 2018", )
    retener_impuesto_renta = fields.Boolean('Retener el Anticipo de I.R.', default=True, )
    fondos_reserva_rol = fields.Boolean('Pagar fondos de reserva en rol', )
    decimo_tercero_rol = fields.Boolean('Pagar décimo tercero en rol', )
    decimo_cuarto_rol = fields.Boolean('Pagar décimo cuarto en rol', )
    gratificacion = fields.Float('Gratificación ($)', )
    provisionar_vacaciones = fields.Boolean('Provisionar vacaciones mensualmente', )
    impuesto_renta = fields.Float(
        string='Impuesto a la renta a pagar ($)',
        help='Dejar en cero si se desea que el sistema calcule el impuesto a pagar',
    )
    basic_wage = fields.Boolean(_('Basic Wage'), oldname='sueldo_basico')
    hour_cost = fields.Float(_('Hour Cost'), compute='_get_hour_cost', store=True)
    prestamos = fields.One2many(
        'hr.contract.prestamo', 'hr_contract_id',
        string='Préstamos / Adelantos', )
    projection_ids = fields.One2many(
        'hr.sri.annual.projection',
        'contract_id',
        string=_('Projection of Personal Expenses'),
    )
    rent_tax_ids = fields.One2many(
        'hr.sri.annual.rent.tax',
        'contract_id',
        string='Tax Rent',
    )
    hist_job_ids = fields.One2many('hr.contract.job', 'contract_id', string=_('Job History'))
    hist_wage_ids = fields.One2many('hr.contract.wage', 'contract_id', string=_('Wage History'))

    @api.model
    def create(self, vals):
        if vals.get('wage'):
            vals['flag'] = True
        return super(HrContract, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('wage'):
            vals['flag'] = True
        return super(HrContract, self).write(vals)

    @api.multi
    @api.depends('wage')
    def _get_hour_cost(self):
        for row in self:
            row.hour_cost = row.wage / 240

    @api.constrains('employee_id', 'active')
    def _check_active_contract(self):
        for row in self:
            contract_ids = [x.id for x in self.search(
                [('employee_id', '=', row.employee_id.id), ('active', '=', True)])]
            contract_ids.remove(row.id)
            if len(contract_ids) >= 1:
                raise UserError(_('¡You can only register one active contract per employee!'))

    @api.constrains('wage')
    def _check_wage(self):
        for row in self:
            if not row.wage or row.wage == 0:
                raise UserError(_('¡You can not save a contract with salary equal to zero!'))


class HrContractJob(models.Model):
    """
    Historical record of job changes
    """
    _name = 'hr.contract.job'
    _description = __doc__

    name = fields.Char(_('Reason'))
    contract_id = fields.Many2one('hr.contract', string=_('Contract'))
    old_job_id = fields.Many2one('hr.job', string=_('Old Job'))
    job_id = fields.Many2one('hr.job', string=_('Job'))
    date = fields.Date(_('Update Date'))


class HrContractWage(models.Model):
    """
    Historical record of wage changes
    """
    _name = 'hr.contract.wage'
    _description = __doc__

    name = fields.Char(_('Reason'))
    contract_id = fields.Many2one('hr.contract', string=_('Contract'))
    old_wage = fields.Float(_('Old Wage'))
    wage = fields.Float(_('Wage'))
    date = fields.Date(_('Update Date'))


class hr_contract_prestamo(models.Model):
    _name = 'hr.contract.prestamo'
    _description = 'Prestamos y adelantos'
    _order = 'termina_pago,state desc'

    hr_contract_id = fields.Many2one('hr.contract', string='Contract', required=True)
    type = fields.Selection(
        [
            ('prestamo', 'Prestamos'),
            ('adelanto', 'Adelanto')
        ],
        'Type', required=True)
    subtype = fields.Selection(
        [
            ('quirografario', 'Quirografario'),
            ('hipotecario', 'Hipotecario')
        ],
        'Subtype')
    monto = fields.Float('Monto recurrente', required=True)
    inicia_pago = fields.Date('Pagar desde', required=True)
    termina_pago = fields.Date('Pagar hasta', required=True)
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('run', 'En ejecutar'),
            ('paid', 'Pagado'),
            ('cancel', 'Cancelado'),
        ],
        'Estado', default='draft')
    debit_account_id = fields.Many2one('account.account', string='Cuenta de debito')
    credit_account_id = fields.Many2one('account.account', string='Cuenta de crédito')
    journal_id = fields.Many2one('account.journal', string='Diario')
    move_id = fields.Many2one('account.move', string='Movimiento')
    create_move = fields.Boolean('Crear movimiento')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_run(self):
        if self.type == 'prestamo' or (self.type == 'adelanto' and not self.create_move):
            self.state = 'run'
            return {}

        move_pool = self.env['account.move']
        timenow = datetime.now().strftime('%Y-%m-%d')
        default_partner_id = self.hr_contract_id.employee_id.address_id.id
        name = 'Adelanto a %s (%s)' % (self.hr_contract_id.employee_id.name, timenow)
        move = {
            'narration': name,
            'date': timenow,
            'ref': name,
            'journal_id': self.journal_id.id,
        }

        line_ids = []

        if self.debit_account_id:
            debit_line = (0, 0, {
                'name': name,
                'date': timenow,
                'partner_id': default_partner_id or False,
                'account_id': self.debit_account_id.id,
                'journal_id': self.journal_id.id,
                'debit': self.monto > 0.0 and self.monto or 0.0,
                'credit': self.monto < 0.0 and -self.monto or 0.0,
            })
            line_ids.append(debit_line)

        if self.credit_account_id:
            credit_line = (0, 0, {
                'name': name,
                'date': timenow,
                'partner_id': default_partner_id or False,
                'account_id': self.debit_account_id.id,
                'journal_id': self.journal_id.id,
                'debit': self.monto < 0.0 and -self.monto or 0.0,
                'credit': self.monto > 0.0 and self.monto or 0.0,
            })
            line_ids.append(credit_line)

        move.update({'line_id': line_ids})
        move_id = move_pool.create(move)
        self.move_id = move_id
        move_pool.post([move_id])
        self.state = 'run'

    @api.multi
    def action_paid(self):
        self.state = 'paid'

    @api.multi
    def action_cancel(self):
        move_obj = self.pool.get('account.move')
        try:
            move_obj.button_cancel(self._cr, self._uid, self.move_id.id, context=self._context)
        except:
            raise exceptions.ValidationError("El asiento relacionado a este adelanto no puede ser cancelado, "
                                             "primero reverselo.")
        self.state = 'cancel'
