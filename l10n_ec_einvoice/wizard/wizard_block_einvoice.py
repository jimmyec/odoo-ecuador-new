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
		invoices = self.env['account.invoice'].search([('autorizado_sri','=',False),('type','in',['out_invoice', 'out_refund']),('state','!=','draft')])   

		for invoice in reversed(invoices):
			self._logger.info('Factura %s', invoice.invoice_number)
			invoice.sudo().action_generate_einvoice()
			#invoice.to_send_einvoice = True

	@api.multi
	def action_automatic_send_email(self):
		"""
		Metodo ...
		"""
		invoices = self.env['account.invoice'].search([('to_send_einvoice','=',True),('type','in',['out_invoice','out_refund'])])   

		for invoice in reversed(invoices):
			self._logger.info('Factura %s', invoice.invoice_number)
			invoice.sudo().action_send_einvoice_email()
			invoice.to_send_einvoice = False

	@api.multi
	def action_automatic_eretention(self):
		"""
		Metodo ...
		"""
		retentions = self.env['account.retention'].search([('autorizado_sri','=',False),('in_type','=','ret_in_invoice')])   

		for ret in reversed(retentions):
			self._logger.info('Retencion %s', ret.withholding_number)
			ret.sudo().action_generate_document()
			#invoice.to_send_einvoice = True

	@api.multi
	def action_automatic_send_ret_email(self):
		"""
		Metodo ...
		"""
		retentions = self.env['account.retention'].search([('to_send_einvoice','=',True),('in_type','=','ret_in_invoice')])   

		for ret in reversed(retentions):
			self._logger.info('Retencion %s', ret.withholding_number)
			ret.sudo().action_send_eretention_email()
			ret.to_send_einvoice = False


	# @api.multi
	# def action_report_failures(self):
	# 	"""
	# 	Metodo ...
	# 	"""
	# 	invoices_sri = self.env['account.invoice'].search([('autorizado_sri','=',False),('type','in',['out_invoice', 'out_refund'])])

	# 	if invoices_sri:
	# 		self._logger.info('Las Facturas: ')
	# 		for invoice in invoices_sri:
	# 			self._logger.info('%s', invoice.invoice_number)
	# 		self._logger.info('No han sido autorizadas por el SRI. Por favor revisar.')
	# 		#self.ensure_one()
 #        	template = self.env.ref('l10n_ec_einvoice.email_template_einvoice_report')
 #        	#self.env['mail.template'].browse(template.id).send_mail(invoices_sri, force_send=True, raise_exception=True)
