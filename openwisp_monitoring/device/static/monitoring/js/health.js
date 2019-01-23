django.jQuery(function($) {
    'use strict';
    var health = $('td.field-health_status, ' +
                   '.field-health_status .readonly');
    if (!health) { return; }
    health.addClass('health-' + health.eq(0).text());
});
