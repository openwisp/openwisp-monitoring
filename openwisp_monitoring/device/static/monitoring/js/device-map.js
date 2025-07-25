"use strict";

/*jshint esversion: 8 */
(function ($) {
  const loadingOverlay = $("#device-map-container .ow-loading-spinner");
  const localStorageKey = "ow-map-shown";
  const mapContainer = $("#device-map-container");
  const statuses = ["critical", "problem", "ok", "unknown", "deactivated"];
  window._owGeoMapConfig.STATUS_COLORS = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#000",
  };
  const colors = window._owGeoMapConfig.STATUS_COLORS;
  const labels = window._owGeoMapConfig.labels;
  const getIndoorCoordinatesUrl = function (pk) {
    return window._owGeoMapConfig.indoorCoordinatesUrl.replace("000", pk);
  };
  const getLocationDeviceUrl = function (pk) {
    return window._owGeoMapConfig.locationDeviceUrl.replace("000", pk);
  };
  const getColor = function (data) {
    let deviceCount = data.device_count,
      findResult = function (func) {
        for (let i in statuses) {
          let status = statuses[i],
            statusCount = data[status + "_count"];
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

    $.ajax({
      dataType: "json",
      url: url,
      xhrFields: {
        withCredentials: true,
      },
      success: function (data) {
        let devices = data.results;
        let nextUrl = data.next;
        const statusLabelsMap = JSON.parse(labels);
        let statusFilterButtons = "";
        console.log(statusLabelsMap);
        Object.entries(statusLabelsMap).forEach(
          ([status_key, status_label]) => {
            const label = gettext(status_label);
            statusFilterButtons += `<span 
              class="health-status health-${status_key} status-filter" 
              data-status="${status_key}"
            >
              ${label}
            </span>`;
          },
        );
        const has_floorplan = data.has_floorplan;
        const floorplan_btn = has_floorplan
          ? `<button class="default-btn floorplan-btn">
          <span class="ow-floor floor-icon"></span>  Switch to Floor Plan
        </button>`
          : "";
        layer.bindPopup(`
                          <div class="map-detail">
                            <h2>${layer.feature.properties.name} (${
                              data.count
                            })</h2>
                            <div class="input-container">
                              <input id="device-search" placeholder="Search for devices" />
                            </div>
                            <div class="label-container">
                              ${statusFilterButtons}
                              <input id="status-filter" style="display: none;" type="text" />
                            </div>
                            <div class="table-container">
                              <table>
                                <thead>
                                    <tr>
                                        <th>${gettext("name")}</th>
                                        <th><span class ="health-status-heading">${gettext(
                                          "status",
                                        )}</span></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    
                                </tbody>
                                </table>
                                <div class="ow-loading-spinner table-spinner"></div>
                            </div>
                            ${floorplan_btn}
                          </div>`);
        layer.openPopup();
        let el = $(layer.getPopup().getElement());
        function renderRows() {
          if (devices.length === 0) {
            el.find("tbody").html(`
              <tr>
                <td class="no-devices">
                  ${gettext("No devices found!")}
                </td>
              </tr>
            `);
            return;
          }
          const rows = devices
            .map(
              (device) => `
            <tr>
                <td><a href="${device.admin_edit_url}">${device.name}</a></td>
                <td>
                    <span class="health-status health-${device.monitoring.status}">
                        ${device.monitoring.status_label}
                    </span>
                </td>
            </tr>
          `,
            )
            .join("");
          el.find("tbody").html(rows);
        }
        let fetchDevicesTimeout;
        let loading = false;
        function fetchDevices(url, ms = 0) {
          if (!url || loading) return;
          clearTimeout(fetchDevicesTimeout);
          loading = true;
          const spinner = el.find(".table-spinner");
          spinner.show();
          fetchDevicesTimeout = setTimeout(() => {
            let params = new URLSearchParams();
            const searchParam = el
              .find("#device-search")
              .val()
              .toLowerCase()
              .trim();
            const statusParam = el.find("#status-filter").val();
            if (searchParam) {
              params.append("search", searchParam);
            }

            if (statusParam) {
              statusParam.split(",").forEach((status) => {
                params.append("status", status);
              });
            }
            const queryString = params.toString();
            let fetchUrl;
            // if nextUrl is the same as url, that means we are fetching for infinite scroll
            if (url === nextUrl) fetchUrl = url;
            else fetchUrl = queryString ? `${url}?${queryString}` : url;

            $.ajax({
              dataType: "json",
              url: fetchUrl,
              xhrFields: { withCredentials: true },

              success(data) {
                if (url === nextUrl) {
                  devices = devices.concat(data.results);
                } else {
                  devices = data.results;
                }
                nextUrl = data.next;
                renderRows(devices);
              },
              error() {
                console.error("Could not load more devices from", url);
              },
              complete() {
                loading = false;
                spinner.hide();
              },
            });
          }, ms);
        }
        renderRows();
        el.find("#device-search").on("input", function () {
          fetchDevices(url, 300);
        });
        let activeStatuses = [];
        el.find(".status-filter").on("click", function (e) {
          e.stopPropagation();
          const btn = $(this);
          const status = btn.data("status");
          const label = gettext(status);

          if (btn.hasClass("active")) {
            btn.removeClass("active").html(label);
            activeStatuses = activeStatuses.filter((s) => s !== status);
          } else {
            btn
              .addClass("active")
              .html(`${label} <span class="remove-icon">&times;</span>`);
            activeStatuses.push(status);
          }
          $(`#status-filter`).val(activeStatuses.join(","));
          fetchDevices(url);
        });
        el.find(".table-container").on("scroll", function () {
          if (this.scrollTop + this.clientHeight >= this.scrollHeight - 10) {
            fetchDevices(nextUrl, 100);
          }
        });
        $(".floorplan-btn").on("click", function () {
          const floorplanUrl = getIndoorCoordinatesUrl(layer.feature.id);
          window.openFloorPlan(floorplanUrl);
        });
        loadingOverlay.hide();
      },
      error: function () {
        loadingOverlay.hide();
        alert(gettext("Error while retrieving data"));
      },
    });
  };
  const leafletConfig = JSON.parse($("#leaflet-config").text());
  const tiles = leafletConfig.TILES.map((tile) => {
    let tileLayer = tile[1];
    if (tileLayer.includes("https:")) {
      tileLayer = tileLayer.split("https:")[1];
    }
    let options = {};
    if (typeof tile[2] === "object") {
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
      mapContainer.find(".no-data").fadeIn(500);
      loadingOverlay.hide();
      mapContainer.find(".no-data").click(function (e) {
        e.preventDefault();
        mapContainer.slideUp();
        localStorage.setItem(localStorageKey, "false");
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
      el: "#device-map-container",
      render: "map",
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
            color: "rgba(0, 0, 0, 0.3)",
            weight: 3,
            opacity: 1,
            fillOpacity: 0.7,
          };
        },
        onEachFeature: function (feature, layer) {
          const color = getColor(feature.properties);
          feature.properties.status = Object.keys(colors).filter(
            (key) => colors[key] === color,
          )[0];

          layer.on("mouseover", function () {
            layer.unbindTooltip();
            if (!layer.isPopupOpen()) {
              layer.bindTooltip(feature.properties.name).openTooltip();
            }
          });
          layer.on("click", function () {
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
        if (leafletConfig.SCALE === "metric") {
          scale.metric = true;
        } else if (leafletConfig.SCALE === "imperial") {
          scale.imperial = true;
        } else if (leafletConfig.SCALE === "both") {
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
          layer[
            layer.feature.geometry.type == "Point"
              ? "bringToFront"
              : "bringToBack"
          ]();
        });

        // Workaround for https://github.com/openwisp/openwisp-monitoring/issues/462
        map.setMaxBounds(
          L.latLngBounds(L.latLng(-90, -540), L.latLng(90, 540)),
        );
        map.on("moveend", (event) => {
          let netjsonGraph = this;
          let bounds = event.target.getBounds();
          if (
            bounds._southWest.lng < -180 &&
            !netjsonGraph.westWorldFeaturesAppended
          ) {
            let westWorldFeatures = window.structuredClone(netjsonGraph.data);
            // Exclude the features that may be added for the East world map
            westWorldFeatures.features = westWorldFeatures.features.filter(
              (element) =>
                !element.geometry || element.geometry.coordinates[0] <= 180,
            );
            westWorldFeatures.features.forEach((element) => {
              if (element.geometry) {
                element.geometry.coordinates[0] -= 360;
              }
            });
            netjsonGraph.utils.appendData(westWorldFeatures, netjsonGraph);
            netjsonGraph.westWorldFeaturesAppended = true;
          }
          if (
            bounds._northEast.lng > 180 &&
            !netjsonGraph.eastWorldFeaturesAppended
          ) {
            let eastWorldFeatures = window.structuredClone(netjsonGraph.data);
            // Exclude the features that may be added for the West world map
            eastWorldFeatures.features = eastWorldFeatures.features.filter(
              (element) =>
                !element.geometry || element.geometry.coordinates[0] >= -180,
            );
            eastWorldFeatures.features.forEach((element) => {
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
          while (
            res.next &&
            data.features.length <= this.config.maxPointsFetched
          ) {
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

  if (localStorage.getItem(localStorageKey) === "false") {
    mapContainer.slideUp(50);
  }
  $.ajax({
    dataType: "json",
    url: window._owGeoMapConfig.geoJsonUrl,
    xhrFields: {
      withCredentials: true,
    },
    success: onAjaxSuccess,
    error: function () {
      mapContainer.find(".no-data").fadeIn(500);
      loadingOverlay.hide();
      mapContainer.find(".no-data").click(function (e) {
        e.preventDefault();
        mapContainer.slideUp();
        localStorage.setItem(localStorageKey, "false");
      });
    },
    context: window,
  });
})(django.jQuery);
