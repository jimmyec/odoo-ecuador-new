# -*- coding: utf-8 -*-
{
    'name': "Payroll for Ecuador",
    'summary': """
        Human resources managment for Ecuador""",
    'category': "Localization/Payroll",
    'description': """
        Payroll management for Ecuador:

        - Adelantos
        - Payroll
        - Prestamos
    """,

    'author': "jfinlay@riseup.net",
    'website': "http://www.lalibre.net",
    'version': '10.0.0.1',
    'depends': [
        'base',
        'hr',
        'hr_payroll',
        'hr_payroll_account',
        'hr_holidays',
        'hr_recruitment',
        #'l10n_ec_sri',
        'web_readonly_store'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_data.xml',
        'data/res_company_data.xml',
        'data/hr_deduction.xml',
        'data/hr_sri_retention.xml',
        'data/hr.holidays.status.csv',
        'views/res_company_view.xml',
        'views/hr_contract_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_department_view.xml',
        'views/hr_payroll_view.xml',
        'views/hr_holidays.xml',
        'views/hr_sri_view.xml',
        'wizard/wizard_hr_contract_update_view.xml',
        'data/update_name.xml'
    ],
    'demo': [],
}
