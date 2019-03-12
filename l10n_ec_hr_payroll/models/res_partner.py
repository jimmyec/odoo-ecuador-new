#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    _defaults = {
        'name': lambda self, cr, uid, context: context.get('employee_name', False),
        'vat': lambda self, cr, uid, context: context.get('employee_identification') or context.get('employee_passport')
    }
