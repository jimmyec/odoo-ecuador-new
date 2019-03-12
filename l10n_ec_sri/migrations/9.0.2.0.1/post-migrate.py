# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

from openupgradelib import openupgrade

def compute_sri_invoice_amounts(env):
    inv = env['account.invoice'].search([])
    for i in inv:
        i.compute_sri_invoice_amounts()
        _logger.warning("Calculando valores para factura: %s", i.number)

@openupgrade.migrate(use_env=True)
def migrate(env, version):
    compute_sri_invoice_amounts(env)
