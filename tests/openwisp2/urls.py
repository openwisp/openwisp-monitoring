from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

redirect_view = RedirectView.as_view(url=reverse_lazy('admin:index'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('openwisp_controller.urls')),
    path('', include('openwisp_monitoring.urls')),
    path('api/v1/', include('openwisp_utils.api.urls')),
    path('', redirect_view, name='index'),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))
