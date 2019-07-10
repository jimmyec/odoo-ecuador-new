# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCity(models.Model):
    _name = 'res.country.city'
    _description = 'Cities of a state'

    state_id = fields.Many2one(
        comodel_name='res.country.state',
        ondelete='restrict',
        string='State',
    )
    name = fields.Char(string='City', )
    code = fields.Char(string='Code', )


class ResParish(models.Model):
    _name = 'res.country.parish'
    _description = 'Parishs of a city'

    city_id = fields.Many2one(
        comodel_name='res.country.city',
        ondelete='restrict',
        string='City',
    )
    name = fields.Char(string='Parish', )
    code = fields.Char(string='Code', )
