# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Establecimientos y autorizaciones del SRI',
    'version': '10.0.0.0.0',
    'description': """
        Funcionalidad para controlar establecimientos propios y de partners
    """,
    'summary': """
        Este módulo es parte de la localización ecuatoriana. Agrega la funcionalidad para controlar los establecimientos
        de partners y de la compañia.
    """,
    'author': 'Cristian Salamea',
    'website': 'http://www.ayni.com.ec',
    'license': 'AGPL-3',
    'category': 'Localization',
    'depends': [
  	    'l10n_ec_partner',
        'account'
    ],
    'data': [
        'view/authorisation_view.xml',
        'data/account.ats.doc.csv',
        'data/account.ats.sustento.csv',
        'security/ir.model.access.csv'
    ],
}
