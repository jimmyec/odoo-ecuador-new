# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Limpia provincia y ciudad al pulsar campo pais
    @api.onchange('country_id')
    def push_country(self):
        return{'value': {'state_id': '', 'city_id': '', 'parish_id': ''}}

    @api.onchange('state_id')
    def push_state(self):
        return{'value': {'city_id': '', 'parish_id': ''}}

    @api.onchange('city_id')
    def push_city(self):
        return{'value': {'parish_id': ''}}

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for r in self:
            if r.city_id:
                r.city = r.city_id.name
            else:
                r.city = ''

    city_id = fields.Many2one(
        comodel_name='res.country.city',
        ondelete='restrict',
        string='City',
    )
    parish_id = fields.Many2one(
        comodel_name='res.country.parish',
        ondelete='restrict',
        string='Parish',
    )

    @api.model
    def default_get(self, vals):
        ''' Retorna Ecuador como pais predeterminado '''
        res = super(ResPartner, self).default_get(vals)
        country_ids = self.env['res.country'].search([('code', '=', 'EC')])

        if country_ids:
            res.update({
                'country_id': country_ids[0].id
            })
        return res
