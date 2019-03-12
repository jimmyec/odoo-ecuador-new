# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

from openupgradelib import openupgrade

def fix_tipoem(env):
    """
    tipoem es físico en todos los documentos.
    """
    openupgrade.logged_query(
        env.cr, """
        UPDATE account_invoice
        SET tipoem = 'F'
        """
    )

@openupgrade.migrate(use_env=True)
def migrate(env, version):
    cr = env.cr
    fix_tipoem(env)
