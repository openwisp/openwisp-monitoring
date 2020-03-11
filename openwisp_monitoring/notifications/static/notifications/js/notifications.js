django.jQuery(function($) {
    var description = $('.field-description div.readonly'),
        text = description.text(),
        data = description.length && JSON.parse($('.form-row.field-data div.readonly').text().replace(/'/g, '"')),
        new_desc;
    window.gettext = window.gettext || function (t) { return t };
    if (data.url) {
        new_desc = '<p>' + text + '</p><p class="target"><a href="' + data.url + '" class="button">' +
                   gettext('Open related object') + '</a></p>';
        description.html('');
        description.append(new_desc);
    }
});
