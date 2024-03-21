'use strict';

if (typeof gettext === 'undefined') {
    var gettext = function (word) {
        return word;
    };
}

(function ($) {
    $(function ($) {
        function getObjectIdFromUrl() {
            let objectId;
            try {
                objectId = /\/((\w{4,12}-?)){5}\//.exec(window.location)[0];
            } catch (error) {
                try {
                    objectId = /\/(\d+)\//.exec(window.location)[0];
                } catch (error) {
                    throw error;
                }
            }
            return objectId.replace(/\//g, '');
        }

        let wifiSessionGroup = $('#wifisession_set-group'),
            wifiSessionUrl = $('#monitoring-wifisession-changelist-url').data('url'),
            wifiSessionLinkElement;
        wifiSessionUrl = `${wifiSessionUrl}?device=${getObjectIdFromUrl()}`;
        wifiSessionLinkElement = `
            <div class="inline-quick-link-container">
                <a href="${wifiSessionUrl}"
                    class="button"
                    id="inline-wifisession-quick-link"
                    title="${gettext('View all the the WiFi sessions of this Device')}"
                >
                    ${gettext("View Full History of WiFi Sessions")}
                </a>
            </div>`;
        wifiSessionGroup.append(wifiSessionLinkElement);
    });
}(django.jQuery));
