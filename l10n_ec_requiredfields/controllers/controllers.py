# -*- coding: utf-8 -*-
from odoo import http

# class L10nEcRequiredfields(http.Controller):
#     @http.route('/l10n_ec_requiredfields/l10n_ec_requiredfields/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_ec_requiredfields/l10n_ec_requiredfields/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_ec_requiredfields.listing', {
#             'root': '/l10n_ec_requiredfields/l10n_ec_requiredfields',
#             'objects': http.request.env['l10n_ec_requiredfields.l10n_ec_requiredfields'].search([]),
#         })

#     @http.route('/l10n_ec_requiredfields/l10n_ec_requiredfields/objects/<model("l10n_ec_requiredfields.l10n_ec_requiredfields"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_ec_requiredfields.object', {
#             'object': obj
#         })