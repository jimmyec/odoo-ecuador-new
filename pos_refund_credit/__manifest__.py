# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'POS Refund Credit',
    'version': '11.0.0.1',
    'description': """
        POS Refund Credit Module
    """,
    'summary': """
        Add a new customer field named refund_credit. refund_credit is the sum of all refund invoices in open state
    """,
    'author': 'cgonzalezbrito',
    'license': 'AGPL-3',
    'category': 'Sales',
    'depends': [
        'point_of_sale',
    ],
    'data': [
        'data/credit.xml',
        'views/header.xml',
        'views/pos_refund_credit_view.xml',
    ],
    'qweb': [
        'static/src/xml/pos_refund_credit.xml'
    ],
}
