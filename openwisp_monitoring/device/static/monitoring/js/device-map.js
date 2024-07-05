"use strict";

/*jshint esversion: 8 */
(function ($) {
    const loadingOverlay = $('#device-map-container .ow-loading-spinner');
    const localStorageKey = 'ow-map-shown';
    const mapContainer = $('#device-map-container');
    const statuses = ['critical', 'problem', 'ok', 'unknown'];
    const colors = {
        ok: '#267126',
        problem: '#ffb442',
        critical: '#a72d1d',
        unknown: '#353c44',
    };
    const getLocationDeviceUrl = function (pk) {
        return window._owGeoMapConfig.locationDeviceUrl.replace('000', pk);
    };
    const getColor = function (data) {
        let deviceCount = data.device_count,
            findResult = function (func) {
                for (let i in statuses) {
                    let status = statuses[i],
                        statusCount = data[status + '_count'];
                    if (statusCount === 0) {
                        continue;
                    }
                    return func(status, statusCount);
                }
            };
        // if one status has absolute majority, it's the winner
        let majority = findResult(function (status, statusCount) {
            if (statusCount > deviceCount / 2) {
                return colors[status];
            }
        });
        if (majority) {
            return majority;
        }
        // otherwise simply return the color based on the priority
        return findResult(function (status, statusCount) {
            // if one status has absolute majority, it's the winner
            if (statusCount) {
                return colors[status];
            }
        });
    };
    const loadPopUpContent = function (layer, url) {
        // allows reopening the last page which was opened before popup close
        // defaults to the passed URL or the default URL (first page)
        if (!url) {
            url = layer.url || getLocationDeviceUrl(layer.feature.id);
        }
        layer.url = url;

        loadingOverlay.show();

        $.getJSON(url, function (data) {
            let html = '',
                device;
            for (let i = 0; i < data.results.length; i++) {
                device = data.results[i];
                html += `
                <tr>
                    <td><a href="${device.admin_edit_url}">${device.name}</a></td>
                    <td>
                        <span class="health-status health-${device.monitoring.status}">
                            ${device.monitoring.status_label}
                        </span>
                    </td>
                </tr>`;
            }
            let pagination = '',
                parts = [];
            if (data.previous || data.next) {
                if (data.previous) {
                    parts.push(`<a class="prev" href="#prev" data-url="${data.previous}">&#8249; ${gettext('previous')}</a>`);
                }
                if (data.next) {
                    parts.push(`<a class="next" href="#next" data-url="${data.next}">${gettext('next')} &#8250;</a>`);
                }
                pagination = `<p class="paginator">${parts.join(' ')}</div>`;
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
                </div>`);
            layer.openPopup();

            // bind next/prev buttons
            let el = $(layer.getPopup().getElement());
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
    const leafletConfig = JSON.parse($('#leaflet-config').text());
    const tiles = leafletConfig.TILES.map((tile) => {
        let tileLayer = tile[1];
        if (tileLayer.includes('https:')) {
            tileLayer = tileLayer.split('https:')[1];
        }
        let options = {};
        if (typeof tile[2] === 'object') {
            options = tile[2];
        } else {
            options.attribution = tile[2];
        }
        return {
            label: tile[0],
            urlTemplate: `https:${tileLayer}`,
            options,
        };
    });

    function onAjaxSuccess(data) {
        if (!data.count) {
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
        /* Workaround for https://github.com/openwisp/openwisp-monitoring/issues/462
        Leaflet does not support looping (wrapping) the map. Therefore, to work around
        abrupt automatic map panning due to bounds, we plot markers on three worlds.
        This allow users to view devices around the International Date Line without
        any weird affects.
        */

        /* global NetJSONGraph */
        const map = new NetJSONGraph(data, {
            el: '#device-map-container',
            render: 'map',
            clustering: false,
            // set map initial state.
            mapOptions: {
                center: leafletConfig.DEFAULT_CENTER,
                zoom: leafletConfig.DEFAULT_ZOOM,
                minZoom: leafletConfig.MIN_ZOOM || 1,
                maxZoom: leafletConfig.MAX_ZOOM || 24,
                fullscreenControl: true,
            },
            mapTileConfig: tiles,
            geoOptions: {
                style: function (feature) {
                    return {
                        radius: 9,
                        fillColor: getColor(feature.properties),
                        color: 'rgba(0, 0, 0, 0.3)',
                        weight: 3,
                        opacity: 1,
                        fillOpacity: 0.7,
                    };
                },
                onEachFeature: function (feature, layer) {
                    const color = getColor(feature.properties);
                    feature.properties.status = Object.keys(colors).filter(
                        (key) => colors[key] === color
                    )[0];

                    layer.on('mouseover', function () {
                        layer.unbindTooltip();
                        if (!layer.isPopupOpen()) {
                            layer.bindTooltip(feature.properties.name).openTooltip();
                        }
                    });
                    layer.on('click', function () {
                        layer.unbindTooltip();
                        layer.unbindPopup();
                        loadPopUpContent(layer);
                    });
                },
            },
            onReady: function () {
                const map = this.leaflet;
                let scale = {
                    imperial: false,
                    metric: false,
                };
                if (leafletConfig.SCALE === 'metric') {
                    scale.metric = true;
                } else if (leafletConfig.SCALE === 'imperial') {
                    scale.imperial = true;
                } else if (leafletConfig.SCALE === 'both') {
                    scale.metric = true;
                    scale.imperial = true;
                }

                if (leafletConfig.SCALE) {
                    /* global L */
                    map.addControl(new L.control.scale(scale));
                }

                if (map.geoJSON.getLayers().length === 1) {
                    map.setView(map.geoJSON.getBounds().getCenter(), 10);
                } else {
                    map.fitBounds(map.geoJSON.getBounds());
                }
                map.geoJSON.eachLayer(function (layer) {
                    layer[layer.feature.geometry.type == 'Point' ? 'bringToFront' : 'bringToBack']();
                });

                // Workaround for https://github.com/openwisp/openwisp-monitoring/issues/462
                map.setMaxBounds(
                    L.latLngBounds(L.latLng(-90, -540), L.latLng(90, 540))
                );
                map.on('moveend', event => {
                    let netjsonGraph = this;
                    let bounds = event.target.getBounds();
                    if (bounds._southWest.lng < -180 && !netjsonGraph.westWorldFeaturesAppended) {
                        let westWorldFeatures = window.structuredClone(netjsonGraph.data);
                        // Exclude the features that may be added for the East world map
                        westWorldFeatures.features = westWorldFeatures.features.filter(
                            element => element.geometry.coordinates[0] <= 180
                        );
                        westWorldFeatures.features.forEach(element => {
                            if (element.geometry) {
                                element.geometry.coordinates[0] -= 360;
                            }
                        });
                        netjsonGraph.utils.appendData(westWorldFeatures, netjsonGraph);
                        netjsonGraph.westWorldFeaturesAppended = true;

                    }
                    if (bounds._northEast.lng > 180 && !netjsonGraph.eastWorldFeaturesAppended) {
                        let eastWorldFeatures = window.structuredClone(netjsonGraph.data);
                        // Exclude the features that may be added for the West world map
                        eastWorldFeatures.features = eastWorldFeatures.features.filter(
                            element => element.geometry.coordinates[0] >= -180
                        );
                        eastWorldFeatures.features.forEach(element => {
                            if (element.geometry) {
                                element.geometry.coordinates[0] += 360;
                            }
                        });
                        netjsonGraph.utils.appendData(eastWorldFeatures, netjsonGraph);
                        netjsonGraph.eastWorldFeaturesAppended = true;
                    }
                });
            },
        });
        map.setUtils({
            showLoading: function () {
                loadingOverlay.show();
            },
            hideLoading: function () {
                loadingOverlay.hide();
            },
            paginatedDataParse: async function (JSONParam) {
                let res;
                let data;
                try {
                    res = await this.utils.JSONParamParse(JSONParam);
                    data = res;
                    while (res.next && data.features.length <= this.config.maxPointsFetched) {
                        res = await this.utils.JSONParamParse(res.next);
                        res = await res.json();
                        data.features = data.features.concat(res.features);
                    }
                } catch (e) {
                    /* global console */
                    console.error(e);
                }
                return data;
            },
        });
        map.render();
    }

    if (localStorage.getItem(localStorageKey) === 'false') {
        mapContainer.slideUp(50);
    }
    $.ajax({
        dataType: "json",
        url: window._owGeoMapConfig.geoJsonUrl,
        xhrFields: {
            withCredentials: true
        },
        success: onAjaxSuccess,
        context: window,
    });
})(django.jQuery);
