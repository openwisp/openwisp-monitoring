"use strict";

(function ($) {
  $(document).ready(function () {
    const locationParent = $("fieldset.module.aligned.loci.coords");
    const floorplanParent = $("fieldset.module.aligned.indoor.coords");
    const deviceLocationId = $("#id_devicelocation-0-id").val();
    const locationId = $("#id_devicelocation-0-location").val();
    const floor = $("#id_devicelocation-0-floor").val();
    const geoMapId = "dashboard-geo-map";
    const indoorMapId = `${locationId}:${floor}`;

    const openLocationBtn = `
        <div class="form-row field-location-view-button" style="display: block;">
          <div>
            <div class="flex-container">                              
                <a href="/admin/device_monitoring/map#id=${geoMapId}&nodeId=${locationId}" 
                   id="open-location-btn"
                   class="default-btn"
                   style="color: white; text-decoration: none;">
                     Open Location on Map
                </a>                    
            </div>
          </div>    
        </div>
    `;

    const openIndoorDeviceBtn = `
        <div class="form-row field-indoor-view-button" style="display: block;">
          <div>
            <div class="flex-container">                             
                <a href="/admin/device_monitoring/map#id=${indoorMapId}&nodeId=${deviceLocationId}" 
                   id="open-indoor-device-btn"
                   class="default-btn" 
                   style="color: white; text-decoration: none;">
                     Open Device on Map
                </a>                   
            </div>
          </div>    
        </div>
    `;

    if (locationId) {
      locationParent.append(openLocationBtn);
    }

    if (floor && locationId) {
      floorplanParent.append(openIndoorDeviceBtn);
    }
  });
})(django.jQuery);
