# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'POS Refund',
    'version': '11.0.0.1',
    'description': """
        Ecuador POS Refund Credit Module
    """,
    'summary': """
        Add a new customer field named refund_credit. refund_credit is the sum of all refund invoices in open and paid state.
        - all payments with Credit.
        New credit journal. Code = NCRD
    """,
    'author': 'cgonzalezbrito',
    'license': 'AGPL-3',
    'category': 'Sales',
    'depends': [
        'point_of_sale',
    ],
    'data': [
        'data/credit.xml',
        #'views/header.xml',
        'views/pos_refund_view.xml',
    ],
    'qweb': [
    #    'static/src/xml/pos_refund_credit.xml'
    ],
}
