# -*- coding: utf-8 -*-
from odoo import http

# class L10nEcEinvoiceDep(http.Controller):
#     @http.route('/l10n_ec_einvoice_dep/l10n_ec_einvoice_dep/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_ec_einvoice_dep/l10n_ec_einvoice_dep/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_ec_einvoice_dep.listing', {
#             'root': '/l10n_ec_einvoice_dep/l10n_ec_einvoice_dep',
#             'objects': http.request.env['l10n_ec_einvoice_dep.l10n_ec_einvoice_dep'].search([]),
#         })

#     @http.route('/l10n_ec_einvoice_dep/l10n_ec_einvoice_dep/objects/<model("l10n_ec_einvoice_dep.l10n_ec_einvoice_dep"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_ec_einvoice_dep.object', {
#             'object': obj
#         })