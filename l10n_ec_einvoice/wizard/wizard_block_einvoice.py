# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api

class account_einvoice_wizard(models.TransientModel):
	_name = "wizard.einvoice"
	_description = 'Bloque de Facturas electrónicas'
	_logger = logging.getLogger(_name)
    
	@api.multi
	def action_automatic_einvoice(self):
		"""
		Metodo ...
		"""
		invoices = self.env['account.invoice'].search([('autorizado_sri','=',False),('type','=',['out_invoice', 'out_refund'])])   

		for invoice in reversed(invoices):
			self._logger.info('Factura %s', invoice.invoice_number)
			invoice.sudo().action_generate_einvoice()
			#invoice.to_send_einvoice = True

	@api.multi
	def action_automatic_send_email(self):
		"""
		Metodo ...
		"""
		invoices = self.env['account.invoice'].search([('to_send_einvoice','=',True),('type','=',['out_invoice','out_refund'])])   

		for invoice in reversed(invoices):
			self._logger.info('Factura %s', invoice.invoice_number)
			invoice.sudo().action_send_einvoice_email()
			invoice.to_send_einvoice = False
