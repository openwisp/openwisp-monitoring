from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import reverse_lazy
from django.views.generic import RedirectView

redirect_view = RedirectView.as_view(url=reverse_lazy('admin:index'))

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'', include('openwisp_controller.urls')),
    url(r'', include('openwisp_monitoring.urls')),
    url(r'', include('openwisp_notifications.urls')),
    url(r'^$', redirect_view, name='index'),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))
