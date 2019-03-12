# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

from openupgradelib import openupgrade

#field_renames = [
#    ('account.tax', 'account_tax', 'sri_code', 'impuesto'),
#]

#def delete_legacy_views(env):
#    openupgrade.logged_query(
#        env.cr, """
#        DELETE FROM ir_model_data
#        WHERE name='view_partner_property_form_sri' """
#    )
#    import wdb
#    wdb.set_trace()
def fix_vat(env):
    """
    Copiamos vat_ec en vat en caso de existir vat_ec y
    borramos los caracteres no numéricos de vat.
    """
    openupgrade.logged_query(
        env.cr, """
        UPDATE res_partner
        SET vat = vat_ec
        WHERE vat_ec IS NOT NULL"""
    )
    openupgrade.logged_query(
        env.cr, "UPDATE res_partner SET vat = REGEXP_REPLACE(vat,'[[:alpha:]]', '', 'g');"
    )

#def install_required_modules(cr):
#    modules_to_install = ('account_invoice_refund_link','')
#    openupgrade.logged_query(
#        cr, "update ir_module_module set state='to install' "
#        "where name in {} "
#        "and state in ('uninstalled', 'to remove') ".format(modules_to_install),
#    )

#def uninstall_deprecated_modules(cr):
#    modules_to_uninstall = ('extra_ec_sri_advanced_tax_decl','extra_ec_sri_tax_decl_management','base_vat','l10n_ec_sri_prepare_taxes')
#    openupgrade.logged_query(
#        cr, "update ir_module_module set state='to remove' "
#        "where name in {}  "
#        "and state in ('installed', 'to upgrade') ".format(modules_to_uninstall),
#   )

#    openupgrade.logged_query(
#        cr, "update ir_module_module set state='uninstalled' "
#        "where name in {}"
#        "and state='to install' ".format(modules_to_uninstall),
#    )

@openupgrade.migrate(use_env=True)
def migrate(env, version):
    cr = env.cr
    #delete_legacy_views(env)
    fix_vat(env)
    #install_required_modules(cr)
    #uninstall_deprecated_modules(cr)
    #openupgrade.rename_fields(env, field_renames)
