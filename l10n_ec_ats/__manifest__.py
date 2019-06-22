# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': "Anexo Transaccional Simplificado",
    'version': '11.0.0.1',
    'description': """
        Genera Anexo Transaccional Simplificado en formato XML para
        la declaración de Impuestos en Ecuador.
    """,
    'summary': """
        Este módulo es parte de la localización ecuatoriana.
        Exporta archivos ATS.xml para la declaración de impuestos en Ecuador.
        Migrado por cgonzalezbrito.
    """,
    'author': 'Cristian Salamea <cristian.salamea@ayni.com.ec>',
    'website': 'http://www.ayni.com.ec',
    'license': 'AGPL-3',
    'category': 'Generic Modules/Accounting',
    'depends': [
        'l10n_ec_withholding',
        'account_period',
    ],
    'data': [
        #'security/ir.model.access.csv',
        'wizard/wizard_ats_view.xml',
    ],
}
