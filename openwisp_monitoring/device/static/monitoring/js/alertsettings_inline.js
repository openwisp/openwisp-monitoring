(function ($) {
    $(function () {
        checks = $('[id^="id_monitoring-metric-content_type-object_id"][id $="alertsettings-0-is_active"]');
        checks.parentsUntil('fieldset.djn-fieldset.module').siblings('h2').css('display', 'none');
        checks.closest('fieldset').siblings('h3').css('display', 'none');
        for (var i = 0; i < checks.length; i++) {
            checks[i].addEventListener('click', function () {
                $(`#${this.id}`).parent().parent().siblings().toggle(this.checked);
            });
        }
    });
})(django.jQuery);
