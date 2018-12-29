![Licence](https://img.shields.io/badge/licence-AGPL--3-blue.svg)
[![Travis Status](https://travis-ci.org/odoo-ecuador/odoo-ecuador.svg?branch=10.0)](https://travis-ci.org/odoo-ecuador/odoo-ecuador)
[![Codecov Status](https://codecov.io/gh/odoo-ecuador/odoo-ecuador/branch/10.0/graph/badge.svg)](https://codecov.io/gh/odoo-ecuador/odoo-ecuador/branch/10.0)

Localización de Odoo para Ecuador
=================================

Rama de https://github.com/odoo-ecuador

GRACIAS A LA COMUNIDAD ODOO-ECUADOR!!

Los cambios que he realizado sirven para ejecutar los módulos en Odoo 11.0 y python3.6

---------------------------------------------------------------

Este proyecto implementa todas o casi todas las funcionalidades
requeridas para que Odoo pueda implementarse en cualquier
empresa ecuatoriana.


Referencias de Implementación
-----------------------------

Es importante también recalcar que este proyecto siempre esta activo, esta versión de localización esta en producción en muchos lugares. Te invitamos a incluir en la [Wiki](https://github.com/odoo-ecuador/odoo-ecuador/wiki/Referencia-de-clientes) de referencias a tus clientes en donde has implementado estos módulos, esto lo consideramos importante para dar valor al trabajo en conjunto que se realiza por la comunidad.

Estado de Módulos
-----------------


| MODULO                   | ESTADO    | OBSERVACIONES                           |
|--------------------------|-----------|-----------------------------------------|
| l10n_ec_authorisation    | ESTABLE 10.0|                                         |
| l10n_ec_chart            | ESTABLE 10.0|                                         |
| l10n_ec_einvoice         | ESTABLE 10.0| Pendiente las retenciones electrónicas  |
| l10n_ec_employee         | NO MIGRADO   |                                         |
| l10n_ec_invoice_sequence | ELIMINADO   |                                         |
| l10n_ec_ote              | NO MIGRADO   |                                         |
| l10n_ec_partner          | ESTABLE 10.0  |                                         |
| l10n_ec_pos              | ESTABLE 10.0 |  |
| l10n_ec_withholding      | ESTABLE 10.0   |                                         |
|l10n_ec_picking_invoice|ESTABLE 10.0||


Objetivos principales
---------------------

- Facturación electrónica
- Plan de cuentas para diferentes tipos de empresas, sitio de ref: http://www.supercias.gob.ec
- Documentos contables: Retenciones, liquidaciones de compra, etc.
- Reportes tributarios, sitio de ref: http://www.sri.gob.ec
- Traducción a español (es_EC)

Uso de Módulos
--------------

Para la instalación y uso::

     $ git clone https://github.com/odoo-ecuador/odoo-ecuador.git

Ahora ejecutar odoo agregando al path de módulos::

     $ ./odoo-bin --addons-path=addons,../odoo-ecuador

El comando anterior asume que odoo y odoo-ecuador estan al mismo nivel.

Para escribir pruebas unitarias revisar la [wiki](https://github.com/odoo-ecuador/odoo-ecuador/wiki/Pruebas-Unitarias)
