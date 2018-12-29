# -*- coding: utf-8 -*-
# © <2016> <Cristian Salamea>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

class AccountWithdrawing(models.Model):

    _name = 'account.sale_note'
    
	STATES_VALUE = {'draft': [('readonly', False)]}

    invoice_id = fields.Many2one(
    	'account.invoice', 
    	string='Invoice Reference', 
    	ondelete='cascade', 
    	index=True
    	)
    name = fields.Char(
        'Número',
        size=64,
        readonly=True,
        states=STATES_VALUE,
        copy=False
        )
    partner_id = fields.Many2one(
    	'res.partner',
    	string='Cliente',
    	required=True,
    	states=STATES_VALUE
    	)
    amount_total = fields.Monetary(
        #compute='_compute_total',
        string='Total',
        store=True,
        readonly=True
        )
