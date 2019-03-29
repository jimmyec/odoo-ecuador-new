# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

class PosSession(models.Model):
	_inherit = 'pos.session'

	def closing_control_print(self):
		return self.env.ref('l10n_ec_pos.report_closing_control').report_action(self)
		