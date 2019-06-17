odoo.define('l10n_ec_pos_refund', function(require){
"use strict";

    var models = require('point_of_sale.models');
    
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
