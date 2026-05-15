"use strict";

(function ($) {
  const loadingOverlay = $("#dashboard-map-overlay .ow-loading-spinner");
  const localStorageKey = "ow-map-shown";
  const mapContainer = $("#device-map-container");
  const statuses = ["critical", "problem", "ok", "unknown", "deactivated"];
  window._owGeoMapConfig.STATUS_COLORS = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#000000",
  };
  const STATUS_COLORS = window._owGeoMapConfig.STATUS_COLORS;
  const STATUS_LABELS = window._owGeoMapConfig.labels;
  const getIndoorCoordinatesUrl = function (pk) {
    return window._owGeoMapConfig.indoorCoordinatesUrl.replace("000", pk);
  };
  const getLocationDeviceUrl = function (pk) {
    return window._owGeoMapConfig.locationDeviceUrl.replace("000", pk);
  };
  const escapeHtml = function (text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
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
        return STATUS_COLORS[status];
      }
    });
    if (majority) {
      return majority;
    }
    // otherwise simply return the color based on the priority
    return findResult(function (status, statusCount) {
      // if one status has absolute majority, it's the winner
      if (statusCount) {
        return STATUS_COLORS[status];
      }
    });
  };

  let currentPopup = null;
  let currentPopupLocationId = null;

  const loadPopUpContent = function (nodeData, netjsongraphInstance, url) {
    loadingOverlay.show();
    const map = netjsongraphInstance.leaflet;
    const locationId = nodeData?.properties?.id || nodeData.id;
    url = url || getLocationDeviceUrl(locationId);

    if (currentPopup) {
      currentPopup.remove();
    }

    $.ajax({
      dataType: "json",
      url: url,
      xhrFields: { withCredentials: true },
      success: function (data) {
        let devices = data.results;
        let nextUrl = data.next;
        let statusFilterButtons = "";
        Object.entries(STATUS_LABELS).forEach(([status_key, status_label]) => {
          statusFilterButtons += `<span
              class="health-status health-${status_key} status-filter"
              data-status="${status_key}"
            >
              ${gettext(status_label)}
              <span class="remove-icon">&times;</span>
            </span>`;
        });
        const has_floorplan = data.has_floorplan;
        const buttonText = gettext("Switch to Indoor View");
        const floorplan_btn = has_floorplan
          ? `<button class="default-btn floorplan-btn">
          <span class="ow-floor floor-icon"></span> ${buttonText}
        </button>`
          : "";

        const popupTitle = nodeData.label;

        // Determine coordinates for the popup. We support:
        // 1. NetJSONGraph objects (nodeData.location)
        // 2. GeoJSON Point array (nodeData.coordinates)
        // 3. GeoJSON Feature geometry (nodeData.geometry.coordinates)
        // This fallback chain ensures the popup always plots at the correct
        // position regardless of datasource format.
        let latLng;
        if (nodeData.location && typeof nodeData.location.lat === "number") {
          latLng = [nodeData.location.lat, nodeData.location.lng];
        } else if (Array.isArray(nodeData.coordinates)) {
          latLng = [nodeData.coordinates[1], nodeData.coordinates[0]];
        } else if (nodeData.geometry?.coordinates?.length >= 2) {
          latLng = [nodeData.geometry.coordinates[1], nodeData.geometry.coordinates[0]];
        }

        if (!latLng || isNaN(latLng[0]) || isNaN(latLng[1])) {
          console.warn(gettext("Could not determine coordinates for popup"), nodeData);
          loadingOverlay.hide();
          return;
        }

        const popupContent = `
          <div class="map-detail">
            <h2>${escapeHtml(popupTitle)} (${data.count})</h2>
            <div class="input-container">
              <input id="device-search" placeholder="${gettext("Search for devices")}" />
            </div>
            <div class="label-container">
              ${statusFilterButtons}
              <input id="status-filter" type="hidden" />
            </div>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>${gettext("name")}</th>
                    <th class="th-status"><span class ="health-status-heading">${gettext("status")}</span></th>
                  </tr>
                </thead>
                <tbody>${renderRows()}</tbody>
              </table>
              <div class="ow-loading-spinner table-spinner"></div>
            </div>
            ${floorplan_btn}
          </div>
        `;

        currentPopupLocationId = locationId;
        currentPopup = L.popup({
          autoPan: true,
          autoPanPadding: [25, 25],
        })
          .setLatLng(latLng)
          .setContent(popupContent)
          .openOn(map);
        const el = $(currentPopup.getElement());
        function renderRows(deviceList) {
          deviceList = deviceList || devices;
          const popup = $(".map-detail");
          if (deviceList.length === 0) {
            popup.find("tbody").html(`
              <tr>
                <td class="no-devices" colspan="2">
                  ${gettext("No devices found")}
                </td>
              </tr>
            `);
            return "";
          }
          const rows = deviceList
            .map(
              (device) => `
            <tr>
              <td class="col-name"><a href="${device.admin_edit_url}">${escapeHtml(device.name)}</a></td>
              <td class="col-status">
                <span class="health-status health-${device.monitoring.status}">
                  ${escapeHtml(gettext(device.monitoring.status_label))}
                </span>
              </td>
            </tr>
          `,
            )
            .join("");
          popup.find("tbody").html(rows);
          return rows;
        }
        let fetchDevicesTimeout;
        let loading = false;
        function fetchDevices(url, ms = 0, append) {
          if (!url || loading) return;
          clearTimeout(fetchDevicesTimeout);
          loading = true;
          const spinner = el.find(".table-spinner");
          const table = el.find(".table-container table");
          spinner.show();
          table.hide();
          fetchDevicesTimeout = setTimeout(() => {
            let params = new URLSearchParams();
            const searchParam = el.find("#device-search").val().toLowerCase().trim();
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
            // if append is true, that means we are fetching for infinite scroll
            if (append) {
              fetchUrl = url; // url is nextUrl, already contains params
            } else {
              fetchUrl = queryString ? `${url}?${queryString}` : url;
            }
            $.ajax({
              dataType: "json",
              url: fetchUrl,
              xhrFields: { withCredentials: true },
              success(data) {
                if (append) {
                  devices = devices.concat(data.results);
                } else {
                  devices = data.results;
                }
                nextUrl = data.next;
                renderRows(devices);
              },
              error() {
                console.error(gettext("Could not load more devices from"), url);
                alert(gettext("Could not load more devices."));
              },
              complete() {
                loading = false;
                spinner.hide();
                table.show();
              },
            });
          }, ms);
        }
        el.find("#device-search").on("input", function () {
          fetchDevices(url, 300);
        });
        let activeStatuses = [];
        el.find(".status-filter").on("click", function (e) {
          e.stopPropagation();
          const btn = $(this);
          const status = btn.data("status");

          if (btn.hasClass("active")) {
            btn.removeClass("active");
            activeStatuses = activeStatuses.filter((s) => s !== status);
          } else {
            btn.addClass("active");
            activeStatuses.push(status);
          }
          $(`#status-filter`).val(activeStatuses.join(","));
          fetchDevices(url);
        });
        el.find(".table-container").on("scroll", function () {
          if (this.scrollTop + this.clientHeight >= this.scrollHeight - 10) {
            fetchDevices(nextUrl, 100, true);
          }
        });
        el.find(".floorplan-btn").on("click", function () {
          const floorplanUrl = getIndoorCoordinatesUrl(locationId);
          window.openFloorPlan(floorplanUrl, locationId);
        });
        el.find(".leaflet-popup-close-button").on("click", function () {
          const id = netjsongraphInstance.config.bookmarkableActions.id;
          netjsongraphInstance.utils.removeUrlFragment(id);
          currentPopup = null;
          currentPopupLocationId = null;
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
    let options = typeof tile[2] === "object" ? tile[2] : { attribution: tile[2] };
    return { label: tile[0], urlTemplate: `https:${tileLayer}`, options };
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

    if (Array.isArray(data.features)) {
      data.features.forEach((f) => {
        if (f?.id && f.properties && !f.properties.id) {
          f.properties.id = f.id;
        }
      });
    }

    const map = new NetJSONGraph(data, {
      el: "#device-map-container",
      render: "map",
      clustering: true,
      clusteringAttribute: "status",
      clusteringThreshold: 0,
      clusterRadius: 100,
      clusterSeparation: 20,
      disableClusteringAtLevel: 15,
      mapOptions: {
        // Use sensible fallback if the backend does not provide DEFAULT_CENTER.
        center: leafletConfig.DEFAULT_CENTER || [55.78, 11.54],
        zoom: leafletConfig.DEFAULT_ZOOM || 1,
        minZoom: leafletConfig.MIN_ZOOM || 1,
        maxZoom: leafletConfig.MAX_ZOOM || 18,
        fullscreenControl: true,

        // Force tooltips ON for all viewport widths; override library's
        // responsive media rules that hide tooltips under 851px.
        baseOptions: {
          media: [
            {
              query: { minWidth: 0 },
              option: { tooltip: { show: false } },
            },
          ],
        },
      },
      bookmarkableActions: {
        enabled: true,
        id: "dashboard-geo-map",
        zoomLevel: 10,
      },
      mapTileConfig: tiles,
      nodeCategories: Object.keys(STATUS_COLORS).map((status) => ({
        name: status,
        nodeStyle: { color: STATUS_COLORS[status] },
      })),
      // Hide ECharts node labels completely at any zoom level
      showLabelsAtZoomLevel: 0,
      echartsOption: {
        tooltip: {
          show: false, // Completely disable tooltips
        },
      },
      prepareData: function (json) {
        const items = json.nodes || json.features;
        if (Array.isArray(items)) {
          items.forEach((el) => {
            const props = el.properties || {};
            let status = props.status?.toLowerCase();
            if (!status) {
              const color = getColor(props);
              status =
                Object.keys(STATUS_COLORS).find((k) => STATUS_COLORS[k] === color) ||
                "unknown";
            }
            props.status = status;
            props.category = status;
            el.category = status;
            el.label = props.name;
            if (!el.properties) el.properties = props;
          });
        }
        return json;
      },
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
          feature.properties.status = Object.keys(STATUS_COLORS).find(
            (key) => STATUS_COLORS[key] === color,
          );

          layer.on("mouseover", function () {
            if (layer._tooltipDisabled) return;
            layer.unbindTooltip();
            if (!layer.isPopupOpen()) {
              layer.bindTooltip(feature.properties.name).openTooltip();
            }
          });

          layer.on("click", function () {
            const clickedLayer = this;
            // Close any open Leaflet tooltip before showing the popup
            clickedLayer.closeTooltip();
            clickedLayer.unbindTooltip();
            clickedLayer.unbindPopup();
            clickedLayer._tooltipDisabled = true; // block future hovers for this marker

            loadPopUpContent(feature, map);

            // Re-enable tooltip when the popup is closed
            map.leaflet.once("popupclose", function () {
              clickedLayer._tooltipDisabled = false;
            });
          });
        },
      },
      onClickElement: function (type, data) {
        if (type === "node") {
          loadPopUpContent(data, this);
        }
      },
      onReady: function () {
        const map = this;
        let scale = { imperial: false, metric: false };
        if (leafletConfig.SCALE === "metric") {
          scale.metric = true;
        } else if (leafletConfig.SCALE === "imperial") {
          scale.imperial = true;
        } else if (leafletConfig.SCALE === "both") {
          scale.metric = true;
          scale.imperial = true;
        }
        if (leafletConfig.SCALE) {
          map.leaflet.addControl(new L.control.scale(scale));
        }

        try {
          const initialZoom = map.leaflet.getZoom();
          const showLabel = initialZoom >= map.config.showLabelsAtZoomLevel;
          map.echarts.setOption({
            series: [
              {
                label: { show: false },
                emphasis: { label: { show: showLabel } },
              },
            ],
          });
        } catch (e) {
          console.warn(gettext("Unable to set initial label visibility"), e);
        }

        try {
          const features = (map.data && map.data.features) || [];
          if (features.length) {
            // Create a temporary layer just to calculate bounds – do NOT add it to the map
            const tempLayer = L.geoJSON(features);
            const bounds = tempLayer.getBounds();

            if (features.length === 1) {
              map.leaflet.setView(bounds.getCenter(), 10);
            } else {
              map.leaflet.fitBounds(bounds);
            }

            // Make sure points sit above polygons for interaction clarity
            tempLayer.eachLayer((layer) => {
              layer[
                layer.feature.geometry.type === "Point" ? "bringToFront" : "bringToBack"
              ]();
            });
          }
        } catch (err) {
          console.error(gettext("Unable to fit NetJSON bounds:"), err);
        }
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
          console.error(e);
        }
        return data;
      },
      // Added to open popup for a specific location Id in selenium tests
      openPopup: function (locationId) {
        const index = map?.data?.nodes?.findIndex((n) => n.id === locationId);
        const nodeData = map?.data?.nodes?.[index];
        if (index == null || index === -1 || !nodeData) {
          const id = map.config.bookmarkableActions.id;
          map.utils.removeUrlFragment(id);
          console.error(`Node with ID "${locationId}" not found.`);
          return;
        }
        const option = map.echarts.getOption();
        const series = option.series.find(
          (s) => s.type === "scatter" || s.type === "effectScatter",
        );
        const seriesIndex = option.series.indexOf(series);

        const params = {
          componentType: "series",
          componentSubType: series.type,
          dataIndex: index,
          data: {
            ...series.data[index],
            node: nodeData,
          },
          seriesIndex: seriesIndex,
          seriesType: series.type,
        };
        map.echarts.trigger("click", params);
      },
    });
    map.render();
    listenForLocationUpdates(map);
    window._owGeoMap = map;
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
  function listenForLocationUpdates(map) {
    if (!map) {
      return;
    }
    var host = window.location.host,
      protocol = window.location.protocol === "http:" ? "ws" : "wss",
      ws = new ReconnectingWebSocket(protocol + "://" + host + "/ws/loci/location/");
    ws.onmessage = function (e) {
      const data = JSON.parse(e.data);
      const [lng, lat] = data.geometry.coordinates;
      if (currentPopup && data.id === currentPopupLocationId) {
        $(currentPopup.getElement()).hide();
      }
      map.utils.moveNodeInRealTime(data.id, { lng, lat });
      if (currentPopup && data.id === currentPopupLocationId) {
        currentPopup.setLatLng([lat, lng]);
        $(currentPopup.getElement()).show();
      }
    };
  }
})(django.jQuery);
