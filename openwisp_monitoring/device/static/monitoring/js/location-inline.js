"use strict";

(function ($) {
  $(document).ready(function () {
    const location_parent = $("fieldset.module.aligned.loci.coords");
    const floorplan_parent = $("fieldset.module.aligned.indoor.coords");
    const deviceLocationId = $("#id_devicelocation-0-id").val();
    const locationId = $("#id_devicelocation-0-location").val();
    const floor = $("#id_devicelocation-0-floor").val();
    const geoMapId = "dashboard-geo-map";
    const indoorMapId = `${locationId}:${floor}`;

    const open_location_btn = `
        <div class="form-row field-location-view-button" style="display: block;">
          <div>
            <div class="flex-container">                
              <label for="id_devicelocation-0-address">View on Map:</label>                
                <a href="/#id=${geoMapId}&nodeId=${locationId}" 
                   id="open-location-btn"
                   class="default-btn"
                   style="color: white; text-decoration: none;">
                     Open Location
                </a>                    
            </div>
          </div>    
        </div>
    `;

    const open_indoor_device_btn = `
        <div class="form-row field-indoor-view-button" style="display: block;">
          <div>
            <div class="flex-container">                
              <label for="id_devicelocation-0-address">View on Indoor Map:</label>                
                <a href="/#id=${indoorMapId}&nodeId=${deviceLocationId}" 
                   id="open-indoor-device-btn"
                   class="default-btn" 
                   style="color: white; text-decoration: none;">
                     Open Device
                </a>                   
            </div>
          </div>    
        </div>
    `;

    if (locationId) {
      location_parent.append(open_location_btn);
    }

    if (floor && locationId) {
      floorplan_parent.append(open_indoor_device_btn);
    }
  });
})(django.jQuery);
