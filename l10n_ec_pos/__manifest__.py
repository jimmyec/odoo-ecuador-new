# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': "l10n_ec_pos",
    'version': '11.0.0.1',
    'description': """
        Agregar campos del partner requeridos en el POS
    """,
    'summary': """
        Cambios en el POS para Ecuador.
        Migrado por cgonzalezbrito.
    """,
    'author': "Cristian Salamea",
    'website': "http://www.ayni.com.ec",
    'license': 'AGPL-3',
    'category': 'POS',
    'depends': [
        'point_of_sale',
        'l10n_ec_authorisation',
        'account_invoice_refund_link',
        'pos_refund_credit'
    ],
    'data': [
        'data/pos.xml',
        'views.xml',
        'ticket_layout.xml',
        'close_control_report.xml',
        'report_closing_control.xml',
    ],
    'qweb': [
        'static/src/xml/l10n_ec_pos.xml',
        'static/src/xml/pos.xml'
    ]
}
