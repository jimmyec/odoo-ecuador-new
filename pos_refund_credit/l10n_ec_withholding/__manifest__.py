# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Retenciones para Ecuador',
    'version': '11.0.0.1',
    'description': """
        Documentos de Retenciones para Ecuador
    """,
    'summary': """
        Este módulo es parte de la localización ecuatoriana.
        Implementa los documentos de retención para Ecuador.
        Personaliza el cálculo de impuestos.
        Migrado por cgonzalezbrito.
    """,
    'author': 'Cristian Salamea <cristian.salamea@ayni.com.ec>',
    'website': 'http://www.ayni.com.ec',
    'license': 'AGPL-3',
    'category': 'Generic Modules/Accounting',
    'depends': [
        'l10n_ec_authorisation',
        'l10n_ec_tax',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/account.fiscal.position.csv',
        #'data/partner.xml',
        'views/report_account_move.xml',
        'views/reports.xml',
        'views/withholding_view.xml',
    ]
}
