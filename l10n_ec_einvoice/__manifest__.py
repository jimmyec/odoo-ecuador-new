# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Electronic Documents for Ecuador',
    'version': '11.0.0.1',
    'description': """
        Módulo para la generación de Documentos Electrónicos.
    """,
    'summary': """
        Este módulo es parte de la localización ecuatoriana.
        Genera Documentos Electrónicos: facturas y retenciones.
        Migrado por cgonzalezbrito.
    """,
    'author': 'Cristian Salamea',
    'website': 'http://www.ayni.com.ec',
    'license': 'AGPL-3',
    'category': 'Localization',
    'depends': [
        'l10n_ec_withholding',
        'mail',
        'web',
        'contacts',
    ],
    'data': [
        #'security/ir.model.access.csv',
        'data/data_einvoice.xml',
        'data/account.epayment.csv',
        'views/einvoice_view.xml',
        'views/partner_view.xml',
        'views/einvoice_report.xml',
        'views/report_einvoice.xml',
        'views/edocument_layouts.xml',
        'views/eretention_report.xml',
        'views/report_eretention.xml',
        'edi/einvoice_edi.xml',
        'edi/eretention_edi.xml',
        #'edi/email_template_einvoice_report.xml'
    ],
}
