"use strict";

/* jshint -W098 */
function owGeoMapInit(map, _) {
    /* jshint +W098 */
    var $ = django.jQuery,
        loadingOverlay = $('#device-map-container .ow-loading-spinner'),
        localStorageKey = 'ow-map-shown',
        mapContainer = $('#device-map-container'),
        colors = {
            ok: '#267126',
            problem: '#ffb442',
            critical: '#a72d1d',
            unknown: '#353c44',
        },
        getLocationDeviceUrl = function (pk) {
            return window._owGeoMapConfig.locationDeviceUrl.replace('000', pk);
        },
        getColor = function (data) {
            var statuses = ['critical', 'problem', 'ok', 'unknown'],
                deviceCount = data.device_count,
                findResult = function (func) {
                    for (let i in statuses) {
                        var status = statuses[i],
                            statusCount = data[status + '_count'];
                        if (statusCount === 0) {
                            continue;
                        }
                        return func(status, statusCount);
                    }
                };
            // if one status has absolute majority, it's the winner
            var majoriy = findResult(function (status, statusCount) {
                if (statusCount > deviceCount / 2) {
                    return colors[status];
                }
            });
            if (majoriy) {
                return majoriy;
            }
            // otherwise simply return the color based on the priority
            return findResult(function (status, statusCount) {
                // if one status has absolute majority, it's the winner
                if (statusCount) {
                    return colors[status];
                }
            });
        },
        loadPopUpContent = function (layer, url) {
            // allows reopening the last page which was opened before popup close
            // defaults to the passed URL or the default URL (first page)
            if (!url) {
                url = layer.url || getLocationDeviceUrl(layer.feature.id);
            }
            layer.url = url;

            loadingOverlay.show();

            $.getJSON(url, function (data) {
                var html = '',
                    device;
                for (var i = 0; i < data.results.length; i++) {
                    device = data.results[i];
                    html += `
<tr>
<td>
<a href="${device.admin_edit_url}">${device.name}</a>
</td>
<td>
<span class="health-status health-${device.monitoring.status}">
${device.monitoring.status_label}
</span>
</td>
</tr>
`;
                }
                var pagination = '', parts = [];
                if (data.previous || data.next) {
                    if (data.previous) {
                        parts.push(`<a class="prev" href="#prev" data-url="${data.previous}">&#8249; ${gettext('previous')}</a>`);
                    }
                    if (data.next) {
                        parts.push(`<a class="next" href="#next" data-url="${data.next}">${gettext('next')} &#8250;</a>`);
                    }
                    pagination = `
<p class="paginator">
${parts.join(' ')}
</div>
`;
                }
                layer.bindPopup(`
<div class="map-detail">
<h2>${layer.feature.properties.name} (${data.count})</h2>
<table>
<thead>
<tr>
<th>${gettext('name')}</th>
<th>${gettext('status')}</th>
</tr>
</thead>
<tbody>
${html}
</tbody>
</table>
${pagination}
</div>
`);
                layer.openPopup();

                // bind next/prev buttons
                var el = $(layer.getPopup().getElement());
                el.find('.next').click(function () {
                    loadPopUpContent(layer, $(this).data('url'));
                });
                el.find('.prev').click(function () {
                    loadPopUpContent(layer, $(this).data('url'));
                });

                loadingOverlay.hide();

            }).fail(function () {
                loadingOverlay.hide();
                alert(gettext('Error while retrieving data'));
            });
        };

    if (localStorage.getItem(localStorageKey) === 'false') {
        mapContainer.slideUp(50);
    }

    function onAjaxSuccess(data) {
        // show map only if there's anything to show
        if (!data.count) {
            map.off();
            map.remove();
            mapContainer.find('.no-data').fadeIn(500);
            loadingOverlay.hide();
            mapContainer.find('.no-data').click(function (e) {
                e.preventDefault();
                mapContainer.slideUp();
                localStorage.setItem(localStorageKey, 'false');
            });
            return;
        } else {
            localStorage.removeItem(localStorageKey);
            mapContainer.slideDown();
        }

        var geojsonLayer = window.L.geoJSON(data, {
            pointToLayer: function (feature, latlng) {
                return window.L.circleMarker(latlng, {
                    radius: 9,
                    fillColor: getColor(feature.properties),
                    color: "rgba(0, 0, 0, 0.3)",
                    weight: 3,
                    opacity: 1,
                    fillOpacity: 0.7
                });
            },
            onEachFeature: function (feature, layer) {
                layer.on('mouseover', function () {
                    this.unbindTooltip();
                    if (!this.isPopupOpen()) {
                        this.bindTooltip(feature.properties.name).openTooltip();
                    }
                });
                layer.on('click', function () {
                    this.unbindTooltip();
                    this.unbindPopup();
                    loadPopUpContent(layer);
                });
            }
        }).addTo(map);

        //move points to top of polygons
        geojsonLayer.eachLayer(function (layer) {
            layer[layer.feature.geometry.type == 'Point' ? 'bringToFront' : 'bringToBack']();
        });

        map.addControl(new window.L.Control.Fullscreen());

        if (geojsonLayer.getLayers().length === 1) {
            map.setView(geojsonLayer.getBounds().getCenter(), 10);
        } else {
            map.fitBounds(geojsonLayer.getBounds());
            map.setZoom(map.getZoom() - 1);
        }

        loadingOverlay.fadeOut(250);
    }

    $.ajax({
        dataType: "json",
        url: window._owGeoMapConfig.geoJsonUrl,
        xhrFields: { withCredentials: true },
        success: onAjaxSuccess
    });
}
