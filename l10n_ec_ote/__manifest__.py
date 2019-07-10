# -*- coding: utf-8 -*-
{
    'name': "OTE - Ecuador",
    'summary': """Ecuador's Geopolitical Information.""",
    'version': '11.0.1.0.0',
    'author': "Fabrica de Software Libre, Odoo Community Association (OCA)",
    'maintainer': 'Fabrica de Software Libre',
    'website': 'http://www.libre.ec',
    'license': 'AGPL-3',
    'category': 'Localization',
    'depends': [
        'base',
    ],
    'data': [
        'views/res_partner.xml',
        'data/res.country.state.csv',
        'data/res.country.city.csv',
        'data/res.country.parish.csv',
        'data/res_country.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [],
    'test': [],
    'installable': True,
}
