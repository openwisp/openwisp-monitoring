(function ($) {
    'use strict';
    $(function () {
        var isActiveCheckboxes = $('[id^="id_monitoring-metric-content_type-object_id"][id $="alertsettings-0-is_active"]');
        isActiveCheckboxes.each(function(i, checkbox){
            $(checkbox).click(function () {
                $('#' + this.id).parent().parent().siblings().toggle(this.checked);
            });
        });
    });
})(django.jQuery);
