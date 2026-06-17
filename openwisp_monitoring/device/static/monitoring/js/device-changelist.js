(function ($) {
  "use strict";
  window.gettext =
    window.gettext ||
    function (word) {
      return word;
    };
  $(function () {
    function updateButtonText($btn) {
      var $label = $btn.find(".issues-toggle-label");
      if ($btn.attr("aria-expanded") === "true") {
        if ($btn.data("error")) {
          $label.text(gettext("retry"));
        } else {
          $label.text(gettext("hide issues"));
        }
      } else {
        $label.text(gettext("show issues"));
      }
    }

    function showContent($content, $accordion, $btn) {
      $accordion.addClass("expanded");
      $btn.attr("aria-expanded", "true");
      updateButtonText($btn);
    }

    function hideContent($content, $accordion, $btn) {
      $accordion.removeClass("expanded");
      $btn.attr("aria-expanded", "false");
      updateButtonText($btn);
    }

    function fetchIssues($btn, $content, deviceId) {
      var apiUrl =
        window.deviceMetricsApiBaseUrl.replace(
          "00000000-0000-0000-0000-000000000000",
          deviceId,
        ) + "?is_healthy=false";
      $.ajax({
        url: apiUrl,
        type: "GET",
        beforeSend: function () {
          var $spinnerWrapper = $btn.siblings(".spinner-wrapper");
          $spinnerWrapper.html(
            '<div class="ow-loading-spinner issues-loading-spinner"></div>',
          );
        },
        success: function (data) {
          var $spinnerWrapper = $btn.siblings(".spinner-wrapper");
          $spinnerWrapper.empty();
          renderIssues($content, data);
          $btn.data("loaded", true);
        },
        error: function (jqXHR, textStatus, errorThrown) {
          var $spinnerWrapper = $btn.siblings(".spinner-wrapper");
          $spinnerWrapper.empty();
          $content.html("<p>" + gettext("Failed to load issues.") + "</p>");
          $btn.data("error", true);
          updateButtonText($btn);
          console.error(
            "Failed to load unhealthy metrics for device " + deviceId + ":",
            textStatus,
            errorThrown,
          );
        },
      });
    }

    $(document).on("click", ".issues-toggle", function (e) {
      e.preventDefault();
      var $btn = $(this);
      var deviceId = $btn.data("device-id");
      var $content = $btn.siblings(".issues-content");
      var $accordion = $btn.closest(".device-issues-accordion");
      var isExpanded = $btn.attr("aria-expanded") === "true";
      var hasError = $btn.data("error");

      if (isExpanded) {
        if (hasError) {
          // Retry: clear error and fetch again
          $btn.data("error", false);
          $content.empty();
          updateButtonText($btn);
          fetchIssues($btn, $content, deviceId);
        } else {
          // Normal collapse
          hideContent($content, $accordion, $btn);
        }
      } else {
        showContent($content, $accordion, $btn);
        var loaded = $btn.data("loaded");
        if (!loaded) {
          fetchIssues($btn, $content, deviceId);
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
