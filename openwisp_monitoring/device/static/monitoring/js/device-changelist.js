(function ($) {
  "use strict";
  if (typeof gettext === "undefined") {
    var gettext = function (word) {
      return word;
    };
  }
  $(function () {
    function showContent($content, $accordion, $btn) {
      $accordion.addClass("expanded");
      $btn.text(gettext("hide issues"));
      $btn.data("expanded", true);
    }

    function hideContent($content, $accordion, $btn) {
      $accordion.removeClass("expanded");
      $btn.text(gettext("show issues"));
      $btn.data("expanded", false);
    }

    $(document).on("click", ".issues-toggle", function (e) {
      e.preventDefault();
      var $btn = $(this);
      var deviceId = $btn.data("device-id");
      var $content = $btn.siblings(".issues-content");
      var $accordion = $btn.closest(".device-issues-accordion");
      var isExpanded = $btn.data("expanded");

      if (isExpanded) {
        hideContent($content, $accordion, $btn);
      } else {
        if ($content.children().length > 0) {
          showContent($content, $accordion, $btn);
        } else {
          var apiUrl =
            "/api/v1/monitoring/device/" + deviceId + "/metrics/?is_healthy=false";
          $.get(apiUrl, function (data) {
            renderIssues($content, data);
            showContent($content, $accordion, $btn);
          }).fail(function (jqXHR, textStatus, errorThrown) {
            $content.html("<p>" + gettext("Failed to load issues.") + "</p>");
            showContent($content, $accordion, $btn);
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
        // Escape HTML in metric.name to prevent XSS: .text() escapes, .html() retrieves the escaped string
        html += "<li>" + $("<span>").text(metric.name).html() + "</li>";
      });
      html += "</ul>";
      $container.html(html);
    }
  });
})(django.jQuery);
