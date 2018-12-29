# -*- coding: utf-8 -*-
from odoo import http

# class L10nEcSaleNote(http.Controller):
#     @http.route('/l10n_ec_sale_note/l10n_ec_sale_note/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_ec_sale_note/l10n_ec_sale_note/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_ec_sale_note.listing', {
#             'root': '/l10n_ec_sale_note/l10n_ec_sale_note',
#             'objects': http.request.env['l10n_ec_sale_note.l10n_ec_sale_note'].search([]),
#         })

#     @http.route('/l10n_ec_sale_note/l10n_ec_sale_note/objects/<model("l10n_ec_sale_note.l10n_ec_sale_note"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_ec_sale_note.object', {
#             'object': obj
#         })