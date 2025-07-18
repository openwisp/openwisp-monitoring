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
        const uniqueStatus = Array.from(
          new Set(devices.map((d) => d.monitoring.status)),
        );
        let statusFilter = "";
        uniqueStatus.forEach((status) => {
          const label = gettext(status);
          statusFilter += `
             <span 
                class="health-status health-${status} status-filter" 
                data-status="${status}"
              >
                ${label}
              </span>
            `;
        });
        const has_floorplan = data.has_floorplan;
        const floorplan_btn = has_floorplan
          ? `<button class="default-btn floorplan-btn">
          <span class="ow-floor icon"></span>  Switch to Floor Plan
        </button>`
          : "";
        layer.bindPopup(`
                          <div class="map-detail">
                            <h2>${layer.feature.properties.name} (${data.count})</h2>
                            <div class="input-container">
                              <input id="device-search" placeholder="Search for devices" />
                            </div>
                            <div class="label-container">
                              ${statusFilter}
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
                              <div class="ow-loading-spinner" style="display: none; position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);"></div>
                            </div>
                            ${floorplan_btn}
                          </div>`);
        layer.openPopup();
        let el = $(layer.getPopup().getElement());
        function renderRows(devices) {
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
        renderRows(devices);
        el.find("#device-search").on("input", function (e) {
          const q = e.target.value.toLowerCase().trim();
          if (!q) {
            renderRows(devices);
          } else {
            // const filtered = devices.filter((d) => {
            //   return (
            //     d.name.toLowerCase().includes(q) ||
            //     d.mac_address.toLowerCase().includes(q)
            //   );
            // });
            // renderRows(filtered);
            $.ajax({
              dataType: "json",
              url: url + "&search=" + q,
              xhrFields: { withCredentials: true },

              success(data) {
                devices = data.results;
                nextUrl = data.next;
                renderRows(devices);
              },
              error() {
                console.error("Could not load more devices from", url);
                nextUrl = url;
              },
            });
          }
        });
        let activeStatuses = [];
        el.find(".status-filter").on("click", function (e) {
          e.stopPropagation();
          const $badge = $(this);
          const status = $badge.data("status");
          const label = gettext(status);

          if ($badge.hasClass("active")) {
            $badge.removeClass("active").html(label);
            activeStatuses = activeStatuses.filter((s) => s !== status);
          } else {
            $badge
              .addClass("active")
              .html(`${label} <span class="remove-icon">&times;</span>`);
            activeStatuses.push(status);
          }

          let toShow;
          if (activeStatuses.length === 0) {
            toShow = devices;
          } else {
            $.ajax({
              dataType: "json",
              url: url + "&status=" + label,
              xhrFields: { withCredentials: true },

              success(data) {
                devices = data.results;
                nextUrl = data.next;
                renderRows(devices);
              },
              error() {
                console.error("Could not load more devices from", url);
                nextUrl = url;
              },
            });
          }
        });
        let nextUrl = data.next;
        let isLoading = false;

        function loadMoreDevices() {
          if (!nextUrl || isLoading) return;

          isLoading = true;

          const $spinner = el.find(".table-container .ow-loading-spinner");
          $spinner.show();

          const url = nextUrl;
          nextUrl = null;

          $.ajax({
            dataType: "json",
            url,
            xhrFields: { withCredentials: true },

            success(newData) {
              devices = devices.concat(newData.results);
              nextUrl = newData.next;
              renderRows(devices);
            },
            error() {
              console.error("Could not load more devices from", url);
              nextUrl = url;
            },
            complete() {
              isLoading = false;
              $spinner.hide();
            },
          });
        }
        el.find(".table-container").on("scroll", function () {
          if (this.scrollTop + this.clientHeight >= this.scrollHeight - 10) {
            loadMoreDevices(nextUrl);
          }
        });
        $(".floorplan-btn").on("click", function () {
          url = getIndoorCoordinatesUrl(layer.feature.id);
          window.openFloorPlan(url);
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
    context: window,
  });
})(django.jQuery);
