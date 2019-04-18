odoo.define('pos_refund_credit', function(require){
"use strict";

    var models = require('point_of_sale.models');
    //var screens = require('point_of_sale.screens');
    //var rpc = require('web.rpc');

    //var _t = instance.web._t,        
    //    _lt = instance.web._lt;    
    //var QWeb = instance.web.qweb;  

    //instance.web.form.widgets.add('refund_credit', 'instance.pos_refund_credit.WidgetM');
    //models.load_fields('res.partner', ['refund_credit']);

    var _super_pos = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
    //local.WidgetM = instance.web.form.AbstractField.extend({
        initialize: function(session, attributes){
            _super_pos.initialize.call(this, session, attributes);
            //this.$el.html(QWeb.render("WidgetTemplate"));
            this.field_manager.on("load_record", this, function() {
                models.load_fields('res.partner', ['refund_credit']);
                this._trigger();
            });
            return this._super();  
        },
    });
});
