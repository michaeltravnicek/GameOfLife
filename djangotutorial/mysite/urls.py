"""URL configuration for mysite project.

The frontend is a React SPA. Django serves:
  - /admin/   Django admin (staff/superuser only)
  - /api/     DRF JSON endpoints consumed by React
  - /media/   user-uploaded files (via WhiteNoise/dev static)
  - /static/  built static assets
  - /api/schema/swagger/  Swagger UI  (DEBUG only)
  - /api/schema/redoc/    ReDoc        (DEBUG only)
  - everything else → React index.html (client routing)
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from . import views as react_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # JSON API for the React frontend
    path("api/", include("leaderboard.api.urls")),
    path("api/auth/", include("accounts.api.urls")),
    path("api/profiles/", include("accounts.api.profiles_urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]

# React catch-all: must come last so /api/*, /admin/*, /media/*, /static/* match first.
# The (/|$) lets us also reserve the bare prefixes (e.g. /admin with no trailing
# slash) for Django — otherwise React would serve them and show a blank screen.
urlpatterns += [
    re_path(r"^(?!(api|admin|media|static)(/|$)).*$", react_views.react_index, name="react-index"),
]
