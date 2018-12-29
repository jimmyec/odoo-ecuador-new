# -*- coding: utf-8 -*-

{
    'name': "l10n_ec_requiredfields",

    'summary': """
        RUC, CI, Contribuyente
    """,

    'description': """
        Campos requeridos para empresas ecuatorianas
    """,

    'author': "cgonzalezbrito",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Localization',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
