# -*- coding: utf-8 -*-

from itertools import groupby

from odoo import api, models


class ReporteComprobante(models.AbstractModel):

    _name = 'report.l10n_ec_withholding.report_move'

    def groupby(self, lines):
        """
        Agrupa lineas por cuenta contable
        """
        glines = []
        for k, g in groupby(lines, key=lambda r: r.account_id):
            debit = 0
            credit = 0
            for i in g:
                debit += i.debit
                credit += i.credit
            glines.append({
                'code': k.code,
                'name': k.name,
                'debit': debit,
                'credit': credit
            })
        return glines

    @api.model
    def get_report_values(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        return {
            'doc_ids': docids,
            'doc_model': self.model,
            'docs': docs,
            'groupby': self.groupby
        }
