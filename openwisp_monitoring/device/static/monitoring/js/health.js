django.jQuery(function($) {
    'use strict';
    var health = $('td.field-health_status, ' +
                   '.field-health_status .readonly');
    if (!health) { return; }
    $.each(health, function(i, el){
        var row = $(el);
        row.addClass('health-' + row.text());
    });
});
