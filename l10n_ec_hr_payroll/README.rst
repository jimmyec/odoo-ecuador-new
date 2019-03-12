.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=================
Ecuador's Payroll
=================

This module includes the most common salary rules in Ecuador.

Installation
============

To install this module, you need to:

* Add the module to your addons path.
* Install the module as usual.

Configuration
=============

It's integrated with the Leaves management module, you should create leave types according to your needs,
and in the code field, you should use:

- DED66 for leave types that will be subsided by the IESS in 66%.
- DED75 for leave types that will be subsided by the IESS in 75%.
- UNPAID for leave types that will not be paid.
- Leave empty if the leave will be paid at a 100%.

Usage
=====

# TODO


Demostración en runbot
======================

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.odoo-community.org/runbot/repo/github-com-oca-l10n-ecuador-212

Known issues / Roadmap
======================

* The code of all WORK100 code should be changed to sum up all WORK100 days, in order to have the worked days with it's real value instead of using the fixed 30 as it's now.
* Done de above, the paid leaves should use WORK100 as a code, instead of empty.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/l10n-ecuador/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and welcomed feedback
`here <https://github.com/OCA/l10n-ecuador/issues/new?body=module:%20l10n_ec_femd%0Aversion:%209.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Credits
=======

Images
------

* Odoo Community Association: `Icon <https://github.com/OCA/maintainer-tools/blob/master/template/module/static/description/icon.svg>`_.

Contributors
------------

* Jonathan Finlay <jfinlay@lalibre.net>
* Edison Ibañes <edison@openmailbox.org>
* Daniel Alejandro Mendieta <damendieta@gmail.com>
* Fábrica de Software Libre <desarrollo@libre.ec>

Maintainer
----------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit http://odoo-community.org... image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License: AGPL-3
