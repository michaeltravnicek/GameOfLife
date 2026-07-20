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
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_media

from . import views as react_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # JSON API for the React frontend. Versioned so installed mobile app
    # builds can keep calling v1 after the contract changes (a future v2
    # mounts alongside; v1 routes stay until no clients use them).
    path("api/v1/", include("leaderboard.api.urls")),
    path("api/v1/auth/", include("accounts.api.urls")),
    path("api/v1/profiles/", include("accounts.api.profiles_urls")),
]

# Serve user-uploaded media (event images, profile photos, gallery uploads).
#
# IMPORTANT: `django.conf.urls.static.static()` returns NOTHING when DEBUG=False,
# and WhiteNoise only serves STATIC_ROOT — never MEDIA_ROOT. The React catch-all
# below also explicitly excludes `/media/`. So in production (Render, DEBUG=False)
# every /media/<path> request 404s, which is why uploaded images vanish while
# static assets work. Serving through Django's `serve` view works in all envs.
_media_prefix = settings.MEDIA_URL.lstrip("/")
urlpatterns += [
    re_path(rf"^{_media_prefix}(?P<path>.*)$", serve_media, {"document_root": settings.MEDIA_ROOT}),
]

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
    re_path(r"^(?!(?:api|admin|media|static)(?:/|$)).*$", react_views.react_index, name="react-index"),
]
