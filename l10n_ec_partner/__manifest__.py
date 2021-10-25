# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Partner for Ecuador',
    'version': '15.0.1.0.0',
    'description': """
        Campos requeridos para empresas ecuatorianas
    """,
    'summary': """
        RUC, CI, Contribuyente
        Migrado por cgonzalezbrito
    """,
    'author': 'Cristian Salamea',
    'website': 'http://www.ayni.com.ec',
    'license': 'AGPL-3',
    'category': 'Localization',
    'depends': [
        'base'
    ],
    'data': [
        'view/partner_view.xml',
        'data/partner.xml'
    ],
    'external_dependencies': {
        'python': ['stdnum']
    },
    'installable': True,
    'maintainer': 'cgonzalezbrito',
}
