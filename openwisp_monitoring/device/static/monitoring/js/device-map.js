"use strict";

/*jshint esversion: 8 */
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
    // New format: single device node already carries its status
    if (data.status) {
      return colors[data.status] || "#000";
    }
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
      if (statusCount) {
        return colors[status];
      }
      // temporary workaround for deactivated
      return "#000";
    });
  };
  const loadPopUpContent = function (layer, url) {
    // allows reopening the last page which was opened before popup close
    // defaults to the passed URL or the default URL (first page)
    if (!url) {
      const locationId = layer.feature.properties.location_id;
      url = layer.url || getLocationDeviceUrl(locationId);
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
        let html = "",
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
        let pagination = "",
          parts = [];
        if (data.previous || data.next) {
          if (data.previous) {
            parts.push(
              `<a class="prev" href="#prev" data-url="${data.previous}">&#8249; ${gettext("previous")}</a>`,
            );
          }
          if (data.next) {
            parts.push(
              `<a class="next" href="#next" data-url="${data.next}">${gettext("next")} &#8250;</a>`,
            );
          }
          pagination = `<p class="paginator">${parts.join(" ")}</div>`;
        }
        layer.bindPopup(`
                            <div class="map-detail">
                                <h2>${layer.feature.properties.name} (${data.count})</h2>
                                <table>
                                    <thead>
                                        <tr>
                                            <th>${gettext("name")}</th>
                                            <th>${gettext("status")}</th>
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
        el.find(".next").click(function () {
          loadPopUpContent(layer, $(this).data("url"));
        });
        el.find(".prev").click(function () {
          loadPopUpContent(layer, $(this).data("url"));
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

  // Helper: expand aggregated location features into one feature per status with non-zero count
  // function expandAggregatedFeatures(geojson) {
  //   console.log(
  //     "[DEBUG] Starting feature expansion with",
  //     geojson.features.length,
  //     "features",
  //   );
  //   const statusKeys = ["critical", "problem", "ok", "unknown", "deactivated"];
  //   const expanded = [];
  //   geojson.features.forEach((feat) => {
  //     // gather active statuses and their counts
  //     const active = statusKeys
  //       .map((status) => ({
  //         status,
  //         count: feat.properties[`${status}_count`] || 0,
  //       }))
  //       .filter((s) => s.count > 0);
  //
  //     if (active.length === 0) {
  //       console.log(
  //         "[DEBUG] Feature",
  //         feat.id || feat.properties.name,
  //         "has no active statuses (all counts = 0); skipping",
  //       );
  //       return; // nothing to render for this feature
  //     }
  //
  //     console.log(
  //       "[DEBUG] Feature",
  //       feat.id || feat.properties.name,
  //       "has statuses:",
  //       active.map((a) => `${a.status}:${a.count}`).join(", "),
  //     );
  //
  //     // if only one status present, no need to offset
  //     if (active.length === 1) {
  //       const { status, count } = active[0];
  //       const clone = window.structuredClone
  //         ? window.structuredClone(feat)
  //         : JSON.parse(JSON.stringify(feat));
  //       const baseId = feat.id || feat.properties.name;
  //       clone.id = `${baseId}_${status}`;
  //       clone.originalId = baseId; // Store original ID for world wrapping
  //       console.log("[DEBUG] Single status feature, no offset:", clone.id);
  //       clone.properties = { ...clone.properties };
  //       statusKeys.forEach((k) => {
  //         clone.properties[`${k}_count`] = k === status ? count : 0;
  //       });
  //       clone.properties.device_count = count;
  //       clone.properties.status = status;
  //       expanded.push(clone);
  //     } else {
  //       // multiple statuses at same location, offset each around a small circle
  //       const radius = 0.0005; // ~50m offset
  //       const originLat = feat.geometry.coordinates[1];
  //       const originLng = feat.geometry.coordinates[0];
  //       console.log(
  //         "[DEBUG] Multiple statuses at location:",
  //         originLng,
  //         originLat,
  //       );
  //
  //       active.forEach(({ status, count }, idx) => {
  //         // calculate position on circle
  //         const angle = (idx / active.length) * 2 * Math.PI;
  //         const dLat = radius * Math.sin(angle);
  //         const dLng = radius * Math.cos(angle);
  //         console.log(
  //           "[DEBUG] Offset for",
  //           status,
  //           "idx:",
  //           idx,
  //           "angle:",
  //           angle.toFixed(2),
  //           "dLng:",
  //           dLng.toFixed(6),
  //           "dLat:",
  //           dLat.toFixed(6),
  //         );
  //
  //         const clone = window.structuredClone
  //           ? window.structuredClone(feat)
  //           : JSON.parse(JSON.stringify(feat));
  //         const baseId = feat.id || feat.properties.name;
  //         clone.id = `${baseId}_${status}`;
  //         clone.originalId = baseId; // Store original ID for world wrapping
  //         clone.geometry.coordinates = [originLng + dLng, originLat + dLat];
  //         clone.properties = { ...clone.properties };
  //         statusKeys.forEach((k) => {
  //           clone.properties[`${k}_count`] = k === status ? count : 0;
  //         });
  //         clone.properties.device_count = count;
  //         clone.properties.status = status;
  //         console.log(
  //           "[DEBUG] Created offset feature:",
  //           clone.id,
  //           "at",
  //           clone.geometry.coordinates[0].toFixed(6),
  //           clone.geometry.coordinates[1].toFixed(6),
  //         );
  //         expanded.push(clone);
  //       });
  //     }
  //   });
  //   console.log(
  //     "[DEBUG] Expansion complete:",
  //     expanded.length,
  //     "features created",
  //   );
  //   return { ...geojson, features: expanded };
  // }

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
    // Expand aggregated features so each status gets its own feature – this enables
    // the NetJSONGraph clustering algorithm to offset them visually.
    // data = expandAggregatedFeatures(data);

    // Defensive filter: ensure every node has a valid location (lat & lng)
    if (data.nodes) {
      data.nodes = data.nodes
        .filter(function (node) {
          return (
            node.properties &&
            node.properties.location &&
            typeof node.properties.location.lat === "number" &&
            typeof node.properties.location.lng === "number"
          );
        })
        // Inject category attribute for color mapping
        .map(function (node) {
          if (!node.category && node.properties && node.properties.status) {
            node.category = node.properties.status.toLowerCase();
          }
          return node;
        });
    }

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
      clusteringThreshold: 5,
      clusterRadius: 80,
      clusterSeparation: 20,
      disableClusteringAtLevel: 16,
      // set map initial state.
      mapOptions: {
        center: leafletConfig.DEFAULT_CENTER,
        zoom: leafletConfig.DEFAULT_ZOOM,
        minZoom: leafletConfig.MIN_ZOOM || 1,
        maxZoom: leafletConfig.MAX_ZOOM || 24,
        center: [55.78, 11.54],
        zoom: 5,
        minZoom: 1,
        maxZoom: 18,
        fullscreenControl: true,
      },
      mapTileConfig: tiles,
      nodeCategories: Object.keys(colors).map(function (k) {
        return { name: k, nodeStyle: { color: colors[k] } };
      }),
      // ensure each feature gains a category derived from its status
      prepareData: function (json) {
        // Only run this logic for GeoJSON datasets that contain a 'features' array.
        if (json && Array.isArray(json.features)) {
          console.log(
            "[DEBUG] prepareData processing",
            json.features.length,
            "features",
          );

          json.features.forEach(function (f) {
            const st = (f.properties && f.properties.status) || "unknown";
            f.category = st.toLowerCase();
          });

          const categories = [...new Set(json.features.map((f) => f.category))];
          console.log("[DEBUG] Unique categories found:", categories.join(", "));
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
            (key) => colors[key] === color,
          );
          feature.properties.status = feature.properties.status || "unknown";

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

        // Ensure ECharts overlay resizes both on generic size changes
        // *and* when Leaflet toggles fullscreen (some browsers skip the
        // internal "resize" event).
        const resizeOverlay = () => {
          // Force a reflow to ensure the container has its final size
          const container = map.getContainer();
          if (container) {
            void container.offsetHeight;
          }
          
          // Invalidate size to force Leaflet to recalculate map dimensions
          map.invalidateSize({ animate: false });
          
          // Get current center and zoom before any potential view changes
          const center = map.getCenter();
          const zoom = map.getZoom();
          
          // Small delay to ensure the browser has updated the layout
          setTimeout(() => {
            // Restore the view with a small offset to force a redraw
            map.setView(center, zoom, { 
              animate: false,
              reset: true  // Force a reset to ensure tiles are redrawn
            });
            
            // If we have ECharts, resize it too
            if (this.echarts && typeof this.echarts.resize === 'function') {
              this.echarts.resize();
            }
          }, 100);
        };

        // Set up event listeners for various resize scenarios
        map.on('resize', resizeOverlay);
        map.on('fullscreenchange', resizeOverlay);
        
        // Listen for fullscreen changes at the document level as a fallback
        document.addEventListener('fullscreenchange', () => {
          // Small delay to ensure the fullscreen change is complete
          setTimeout(resizeOverlay, 100);
        });
        
        // Also listen for orientation changes on mobile devices
        window.addEventListener('orientationchange', resizeOverlay);
        
        // Initial resize check
        setTimeout(resizeOverlay, 500);

        // Prefer using bounds from the Leaflet geoJSON layer when present (GeoJSON mode).
        if (map.geoJSON && map.geoJSON.getLayers) {
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
        } else {
          // NetJSON mode: derive bounds from node coordinates
          const coords = (this.data && this.data.nodes) || [];
          if (coords.length === 1) {
            map.setView(
              [coords[0].location.lat, coords[0].location.lng],
              10,
            );
          } else if (coords.length > 1) {
            const bounds = L.latLngBounds(
              coords.map(function (n) {
                return L.latLng(n.location.lat, n.location.lng);
              }),
            );
            map.fitBounds(bounds);
          }
        }

        // Fallback: observe the map container for any size changes –
        // this catches browsers/devices that don't emit a fullscreenchange
        // event or when the event fires before our listeners are attached.
        if (window.ResizeObserver) {
          const ro = new ResizeObserver(() => resizeOverlay());
          ro.observe(map.getContainer());
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
          while (
            res.next &&
            ((data.nodes && data.nodes.length <= this.config.maxPointsFetched) ||
              (data.features && data.features.length <= this.config.maxPointsFetched))
          ) {
            res = await this.utils.JSONParamParse(res.next);
            res = await res.json();
            if (data.nodes) {
              data.nodes = data.nodes.concat(res.nodes || []);
            } else if (data.features) {
              data.features = data.features.concat(res.features || []);
            }
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
    url: window._owGeoMapConfig.netJsonUrl,
    xhrFields: {
      withCredentials: true,
    },
    success: onAjaxSuccess,
    context: window,
  });
})(django.jQuery);
