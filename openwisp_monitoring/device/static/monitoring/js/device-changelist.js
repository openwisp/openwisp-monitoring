(function ($) {
  "use strict";
  if (typeof gettext === "undefined") {
    var gettext = function (word) {
      return word;
    };
  }
  $(function () {
    $(document).on("click", ".issues-toggle", function (e) {
      e.preventDefault();
      var $btn = $(this);
      var deviceId = $btn.data("device-id");
      var $content = $btn.siblings(".issues-content");
      var $accordion = $btn.closest(".device-issues-accordion");
      var isExpanded = $btn.data("expanded");

      if (isExpanded) {
        $content.slideUp(200, function () {
          $accordion.removeClass("expanded");
        });
        $btn.text(gettext("show issues"));
        $btn.data("expanded", false);
      } else {
        if ($content.children().length > 0) {
          $content.slideDown(200, function () {
            $accordion.addClass("expanded");
          });
          $btn.text(gettext("hide issues"));
          $btn.data("expanded", true);
        } else {
          var apiUrl =
            "/api/v1/monitoring/device/" + deviceId + "/metrics/?is_healthy=false";
          $.get(apiUrl, function (data) {
            renderIssues($content, data);
            $content.slideDown(200, function () {
              $accordion.addClass("expanded");
            });
            $btn.text(gettext("hide issues"));
            $btn.data("expanded", true);
          }).fail(function (jqXHR, textStatus, errorThrown) {
            $content.html("<p>" + gettext("Failed to load issues.") + "</p>");
            $content.slideDown(200);
            console.error(
              "Failed to load unhealthy metrics for device " + deviceId + ":",
              textStatus,
              errorThrown,
            );
          });
        }
      }
    });

    function renderIssues($container, metrics) {
      if (!metrics || metrics.length === 0) {
        $container.html("<p>" + gettext("No unhealthy metrics found.") + "</p>");
        return;
      }
      var html = "<ul>";
      $.each(metrics, function (i, metric) {
        html += "<li>" + $("<span>").text(metric.name).html() + "</li>";
      });
      html += "</ul>";
      $container.html(html);
    }
  });
})(django.jQuery);
