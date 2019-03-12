#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import api, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    @api.multi
    def name_get(self):
        reads = self.read(['name', 'department_id'])
        res = []
        for record in reads:
            name = record['name']
            if record['department_id']:
                name = record['department_id'][1] + ' / ' + name
            res.append((record['id'], name))
        return res
