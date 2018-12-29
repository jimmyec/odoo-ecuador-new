# -*- coding: utf-8 -*-
{
    'name': "l10n_ec_einvoice_dep",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['l10n_ec_withholding_dep'],

    # always loaded
    'data': [
        #'security/ir.model.access.csv',
        'views/views.xml',
        #'views/templates.xml',
        'data/data_einvoice.xml',
        'data/account.epayment.csv',
        'edi/einvoice_edi.xml',
        'views/partner_view.xml',
        'views/report_einvoice.xml',
        'views/edocument_layouts.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
