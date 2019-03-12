# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    tax_form_ids = fields.Many2many(
        'l10n_ec_sri.tax.form', 'move_tax_form_rel', 'tax_form_ids',
        'move_ids', string="Tax form", )
