'use strict';

(function () {
    document.addEventListener(
        'DOMContentLoaded',
        function () {
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

            let wifiSessionQuickLink = document.getElementById('inline-wifisession-quick-link');
            wifiSessionQuickLink.href += `?device=${getObjectIdFromUrl()}`;
        },
        false
    );
})();
