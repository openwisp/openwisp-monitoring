"use strict";

/* jshint esversion: 8 */
(function ($) {
  const loadingOverlay = $("#device-map-container .ow-loading-spinner");
  const localStorageKey = "ow-map-shown";
  const mapContainer = $("#device-map-container");
  const statuses = ["critical", "problem", "ok", "unknown", "deactivated"];
  const colors = {
    ok: "#267126",
    problem: "#ffb442",
    critical: "#a72d1d",
    unknown: "#353c44",
    deactivated: "#000000",
  };

  const getLocationDeviceUrl = function (pk) {
    return window._owGeoMapConfig.locationDeviceUrl.replace("000", pk);
  };

  const getColor = function (data) {
    let deviceCount = data.device_count;
    let findResult = function (func) {
      for (let i in statuses) {
        let status = statuses[i];
        let statusCount = data[status + "_count"];
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
      // temporary workaround for deactivated
      return "#000";
    });
  };

  let currentPopup = null; // Track the popup currently shown

  const loadPopUpContent = function (nodeData, netjsongraphInstance, url) {
    const map = netjsongraphInstance.leaflet;
    if (!url) {
      const locationId = nodeData?.properties?.id || nodeData.id;
      url = getLocationDeviceUrl(locationId);
    }

    // Close any popup left open
    if (currentPopup) {
      currentPopup.remove();
    }

    loadingOverlay.show();

    $.ajax({
      dataType: "json",
      url: url,
      xhrFields: {
        withCredentials: true,
      },
      success: function (apiData) {
        let html = "";
        let device;
        for (let i = 0; i < apiData.results.length; i++) {
          device = apiData.results[i];
          html += `
            <tr>
              <td><a href="${device.admin_edit_url}">${device.name}</a></td>
              <td>
                <span class="health-status health-${device.monitoring.status}">${device.monitoring.status_label}</span>
              </td>
            </tr>
          `;
        }

        let pagination = "";
        const parts = [];
        if (apiData.previous) {
          parts.push(`<a class="prev" href="#prev" data-url="${apiData.previous}">‹ ${gettext("previous")}</a>`);
        }
        if (apiData.next) {
          parts.push(`<a class="next" href="#next" data-url="${apiData.next}">${gettext("next")} ›</a>`);
        }
        if (parts.length) {
          pagination = `<p class="paginator">${parts.join(" ")}</p>`;
        }

        const popupTitle = nodeData.label || nodeData?.properties?.name || nodeData.id;

        // Determine coordinates (lat, lng)
        let latLng;
        if (nodeData.location && typeof nodeData.location.lat === "number") {
          latLng = [nodeData.location.lat, nodeData.location.lng];
        } else if (Array.isArray(nodeData.coordinates)) {
          // NetJSON nodes use [lng, lat]
          latLng = [nodeData.coordinates[1], nodeData.coordinates[0]];
        } else if (nodeData.geometry && Array.isArray(nodeData.geometry.coordinates)) {
          latLng = [nodeData.geometry.coordinates[1], nodeData.geometry.coordinates[0]];
        }

        if (!latLng || isNaN(latLng[0]) || isNaN(latLng[1])) {
          console.warn("Could not determine coordinates for popup", nodeData);
          return;
        }

        const popupContent = `
          <div class="map-detail">
            <h2>${popupTitle} (${apiData.count})</h2>
            <table>
              <thead>
                <tr><th>${gettext("name")}</th><th>${gettext("status")}</th></tr>
            </thead>
            <tbody>${html}</tbody>
          </table>
          ${pagination}
        </div>
      `;

        /* global L */
        currentPopup = L.popup()
          .setLatLng(latLng)
          .setContent(popupContent)
          .openOn(map);

        // Bind pagination links
        const $el = $(currentPopup.getElement());
        $el.find(".next").click(function (e) {
          e.preventDefault();
          loadPopUpContent(nodeData, netjsongraphInstance, $(this).data("url"));
        });
        $el.find(".prev").click(function (e) {
          e.preventDefault();
          loadPopUpContent(nodeData, netjsongraphInstance, $(this).data("url"));
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

    // Propagate each GeoJSON feature.id into feature.properties.id so the
    // GeoJSON→NetJSON conversion preserves the real UUID instead of generating
    // a synthetic `gjn_XXX` id.
    if (Array.isArray(data.features)) {
      data.features.forEach((f) => {
        if (f && f.id && f.properties && !f.properties.id) {
          f.properties.id = f.id;
        }
      });
    }

    // Expand aggregated features so each status gets its own feature – this enables
    // the NetJSONGraph clustering algorithm to offset them visually.
    // data = expandAggregatedFeatures(data);

    /* Workaround for https://github.com/openwisp/openwisp-monitoring/issues/462
        Leaflet does not support looping (wrapping) the map. Therefore, to work around
        abrupt automatic map panning due to bounds, we plot markers on three worlds.
        This allows users to view devices around the International Date Line without
        any weird affects.
        */

    /* global NetJSONGraph */
    const map = new NetJSONGraph(data, {
      el: "#device-map-container",
      render: "map",
      clustering: true,
      clusteringAttribute: "status",
      clusteringThreshold: 0,
      clusterRadius: 100,
      clusterSeparation: 20,
      disableClusteringAtLevel: 16,
      // set map initial state.
      mapOptions: {
        center:
          leafletConfig.CENTER ||
          leafletConfig.DEFAULT_CENTER ||
          [55.78, 11.54],
        zoom:
          leafletConfig.ZOOM ||
          leafletConfig.DEFAULT_ZOOM ||
          1,
        minZoom: leafletConfig.MIN_ZOOM || 1,
        maxZoom: leafletConfig.MAX_ZOOM || 18,
        fullscreenControl: true,
      },
      mapTileConfig: tiles,
      nodeCategories: Object.keys(colors).map((k) => ({
        name: k,
        nodeStyle: { color: colors[k] },
      })),
      echartsOption: {
        tooltip: {
          confine: true,
          formatter: function (params) {
            let n = null;
            if (params.data && params.data.node) {
              n = params.data.node;
            } else if (params.data) {
              n = params.data;
            }
            if (n) {
              return (
                (n.properties && n.properties.name) ||
                n.label ||
                n.id ||
                ""
              );
            }
            return "";
          },
        },
      },
      // ensure each element is categorised by status so clustering & styles work
      prepareData: function (json) {
        const items = json.nodes || json.features;

        if (Array.isArray(items)) {
          items.forEach((el) => {
            const props = el.properties || {};

            // Derive status:
            let status;

            if (props.status) {
              status = props.status.toLowerCase();
            } else {
              // Fallback: use same heuristic used later in onEachFeature
              const color = getColor(props);
              status =
                Object.keys(colors).find((k) => colors[k] === color) ||
                "unknown";
            }

            // Ensure both 'status' and 'category' are populated for clustering & styling
            props.status = status;
            el.category = status;
            props.category = status;

            // In case we created a fresh properties object, re-attach it
            if (!el.properties) {
              el.properties = props;
            }
          });
        }

        return json;
      },
      geoOptions: {
        style: function (feature) {
          return {
            radius: 9,
            fillColor: getColor(feature.properties),
            // color: "rgba(0, 0, 0, 0.3)",
            weight: 3,
            opacity: 0,
            fillOpacity: 0.7,
          };
        },
        onEachFeature: function (feature, layer) {
          const color = getColor(feature.properties);
          feature.properties.status = Object.keys(colors).find(
            (k) => colors[k] === color,
          );
          feature.properties.status = feature.properties.status || "unknown";

          layer.on("mouseover", function () {
            layer.unbindTooltip();
            if (!layer.isPopupOpen()) {
              layer.bindTooltip(feature.properties.name).openTooltip();
            }
          });
        },
      },
      onClickElement: function (type, data) {
        if (type === "node") {
          loadPopUpContent(data, this);
        } else if (type === "Feature") {
          console.log("Clicked a GeoJSON Feature:", data);
        }
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

        // Some NetJSONGraph versions attach the marker layer to
        // `leaflet.geoJSON` only *after* the `onReady` callback fires.
        // Safely access the layer if present; otherwise skip these niceties.
        const geoLayer = map.geoJSON;
        if (geoLayer) {
          if (geoLayer.getLayers().length === 1) {
            map.setView(geoLayer.getBounds().getCenter(), 10);
          } else {
            map.fitBounds(geoLayer.getBounds());
          }

          geoLayer.eachLayer(function (layer) {
            layer[
              layer.feature &&
              layer.feature.geometry &&
              layer.feature.geometry.type == "Point"
                ? "bringToFront"
                : "bringToBack"
            ] &&
              layer[
                layer.feature &&
                layer.feature.geometry &&
                layer.feature.geometry.type == "Point"
                  ? "bringToFront"
                  : "bringToBack"
              ]();
          });
        }

        // Workaround for https://github.com/openwisp/openwisp-monitoring/issues/462
        map.setMaxBounds(
          L.latLngBounds(L.latLng(-90, -540), L.latLng(90, 540)),
        );
        map.on("moveend", (event) => {
          let netjsonGraph = this;
          let bounds = event.target.getBounds();
          let needsRefresh = false;
          console.log(
            "[DEBUG] Map moveend event, bounds:",
            bounds._southWest.lng,
            bounds._northEast.lng,
          );
        
          const isGeoJSON = Array.isArray(netjsonGraph.data?.features);

          if (
            isGeoJSON &&
            bounds._southWest.lng < -180 &&
            !netjsonGraph.westWorldFeaturesAppended
          ) {
            let westWorldFeatures = window.structuredClone(netjsonGraph.data);
            westWorldFeatures.features = westWorldFeatures.features.filter(
              (element) =>
                !element.geometry || element.geometry.coordinates[0] <= 180,
            );
            westWorldFeatures.features.forEach((element) => {
              if (element.geometry) {
                element.geometry.coordinates[0] -= 360;
                if (element.id) {
                  element.id = `west_${element.id}`;
                  if (element.category) {
                    element.originalCategory = element.category;
                  }
                }
              }
            });
            netjsonGraph.utils.appendData(westWorldFeatures, netjsonGraph);
            netjsonGraph.westWorldFeaturesAppended = true;
            needsRefresh = true;
          }
        
          if (
            isGeoJSON &&
            bounds._northEast.lng > 180 &&
            !netjsonGraph.eastWorldFeaturesAppended
          ) {
            let eastWorldFeatures = window.structuredClone(netjsonGraph.data);
            eastWorldFeatures.features = eastWorldFeatures.features.filter(
              (element) =>
                !element.geometry || element.geometry.coordinates[0] >= -180,
            );
            eastWorldFeatures.features.forEach((element) => {
              if (element.geometry) {
                element.geometry.coordinates[0] += 360;
                if (element.id) {
                  element.id = `east_${element.id}`;
                  if (element.category) {
                    element.originalCategory = element.category;
                  }
                }
              }
            });
            netjsonGraph.utils.appendData(eastWorldFeatures, netjsonGraph);
            netjsonGraph.eastWorldFeaturesAppended = true;
            needsRefresh = true;
          }
        
          // Force refresh clustering if features were added
          if (needsRefresh) {
            // Reset and rebuild clusters
            console.log("[DEBUG] Refreshing clusters after world wrapping");
            netjsonGraph.leaflet.geoJSON.clearLayers();
            netjsonGraph.render();
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
