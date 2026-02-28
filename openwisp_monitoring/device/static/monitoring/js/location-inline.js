"use strict";

(function ($) {
  $(document).ready(function () {
    const locationParent = $("fieldset.module.aligned.loci.coords");
    const floorplanParent = $("fieldset.module.aligned.indoor.coords");
    const deviceLocationId = $("#id_devicelocation-0-id").val();
    const locationId = $("#id_devicelocation-0-location").val();
    const floor = $("#id_devicelocation-0-floor").val();
    const geoMapId = `id=dashboard-geo-map&nodeId=${locationId}`;

    if (!locationId) {
      return;
    }

    const openLocationBtn = `
      <div class="form-row field-location-view-button view-on-map-div">
        <div>
          <div class="flex-container">
            <label for="id_devicelocation-0-map">${gettext("Map:")}</label>
            <a href="/admin/device_monitoring/map#${geoMapId}"
              id="open-location-btn"
              class="default-btn view-on-map-btn">
                ${gettext("View on General Map")}
            </a>
          </div>
          <div class="help" id="id_devicelocation-0-map_helptext">
            <div>${gettext("Opens the general map view focused on this location")}</div>
          </div>
        </div>
      </div>
    `;
    locationParent.append(openLocationBtn);

    if (!floor) {
      return;
    }

    const indoorMapId = `id=${locationId}:${floor}&nodeId=${deviceLocationId}`;
    const openIndoorDeviceBtn = `
      <div class="form-row field-indoor-view-button view-on-map-div">
        <div>
          <div class="flex-container">
            <label for="id_devicelocation-0-indoor_map">${gettext("Map:")}</label>
            <a href="/admin/device_monitoring/map#${geoMapId};${indoorMapId}"
              id="open-indoor-device-btn"
              class="default-btn view-on-map-btn">
                ${gettext("View on General Indoor Map")}
            </a>
          </div>
          <div class="help" id="id_devicelocation-0-indoor_map_helptext">
            <div>${gettext("Opens the general indoor map view focused on this device")}</div>
          </div>
        </div>
      </div>
    `;
    floorplanParent.append(openIndoorDeviceBtn);
  });
})(django.jQuery);
