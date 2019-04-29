odoo.define('l10n_ec_pos', function(require) {
"use strict";

    var PosDB = require('point_of_sale.DB');
    var models = require('point_of_sale.models');
    var screens = require('point_of_sale.screens');

    var clave_acceso;
    var number;

    PosDB.include({

        _partner_search_string: function(partner){
            var str =  partner.name;
            if(partner.identifier){
	        str += '|' + partner.identifier;
            }
            if(partner.ean13){
                str += '|' + partner.ean13;
            }
            if(partner.address){
                str += '|' + partner.address;
            }
            if(partner.phone){
                str += '|' + partner.phone.split(' ').join('');
            }
            if(partner.mobile){
                str += '|' + partner.mobile.split(' ').join('');
            }
            if(partner.email){
                str += '|' + partner.email;
            }
            str = '' + partner.id + ':' + str.replace(':','') + '\n';
            return str;
        }

    });

    var pos_models = models.PosModel.prototype.models;
    var _super_order_model = models.Order.prototype;

    var _super_pos_model = models.PosModel.prototype;

    var rpc = require('web.rpc');
    var core = require('web.core');

    models.Order = models.Order.extend({

	    initialize: function(attributes,options){
            _super_order_model.initialize.call(this, attributes, options);
            var customer = this.pos.db.get_partner_by_id(this.pos.config.default_partner_id[0]);
            if (!customer){
                console.log('WARNING: no default partner in POS');
            }else{
                this.set({ client: customer });
            }
            this.sequence = {};
        },
    });

    screens.ReceiptScreenWidget.include({
        render_receipt: function(){

            var self = this;
            
            var date = moment().format('DDMMYYYY');
            var tcomp = '01';
            var ruc = this.pos.company.vat;
            var env = this.pos.company.env_service;
            var journal = this.pos.config.invoice_journal_id[0];
            var mod;

            var QWeb = core.qweb;

            rpc.query({
                model: 'pos.order',
                method: 'get_inv_number',
                args:[
                    [''],
                    [journal],
                ],
            }).then(function(numero){
                number = numero
                rpc.query({
                    model: 'account.invoice',
                    method: 'get_pos_code',
                    args:[{
                        'arg1': '',
                    }],
                }).then(function (code){
                    clave_acceso = date + tcomp + ruc + env + numero + code + '1';
                    mod = self.compute_mod11(clave_acceso);
                    clave_acceso += mod;
                    self.$('.pos-receipt-container').html(QWeb.render('PosTicket', self.get_receipt_render_env()));    
                    console.log(clave_acceso)
                    // alert('ALERTA')
                });
            });
        },
        compute_mod11: function(value){
            var total = 0;
            var weight = 2;

            for (var i = value.length - 1; i >= 0; i--) {
                total += parseInt(value[i])*weight;
                weight += 1;
                if (weight > 7){
                    weight = 2;
                }
            }
            var mod = 11 - total%11;
            if (mod === 11){return 0;} else if (mod === 10 ) {return 1;} else {return mod;}
        },
        get_clave_start: function(){
            return clave_acceso.substr(0,25)
        },
        get_clave_end: function(){
            return clave_acceso.substr(26,49);
        },
        get_invoice_number: function(){
            return number
        },
        get_env_service: function(){
            if (this.pos.company.env_service === 2) {return 'PRODUCCIÓN'} else {return 'PRUEBAS'}
        },
    });

    for (var i=0; i<pos_models.length; i++){
        var model = pos_models[i];
        if (model.model === 'res.partner') {
            model.fields.push('identifier', 'type_id', 'tipo_persona','refund_credit');
        }
        if (model.model === 'res.company') {
	        model.fields.push('street', 'env_service', 'namerl');
        }
    }
});
