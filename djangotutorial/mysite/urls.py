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
import os

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control
from django.views.static import serve as serve_media

from . import views as react_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Deliberate 500 for verifying the Sentry pipeline. Superuser-only —
    # see the view's docstring for why it isn't the open route Sentry suggests.
    path("sentry-debug/", react_views.sentry_debug, name="sentry-debug"),

    # Proxy-chain diagnostic (superuser only) — used to confirm PROXY_COUNT
    # matches reality, since getting it wrong silently breaks rate limiting.
    path("whoami/", react_views.whoami, name="whoami"),

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
#
# CACHING: `serve` sends no Cache-Control at all, so Cloudflare classed every
# image as `cf-cache-status: DYNAMIC` and forwarded 100% of image traffic to
# Render — a CDN sitting in front of the site while providing no relief for the
# single heaviest thing it serves. Declaring the response public and cacheable
# lets the edge (and the browser) hold it, so a worker isn't tied up per image.
#
# Safe here because media filenames are effectively immutable: Django appends a
# random suffix on collision, so replacing an event image produces a NEW URL
# rather than changing the bytes behind an existing one. `immutable` is left
# off deliberately — it forbids revalidation entirely, and a month is a long
# time to be unable to correct a mistake.
# The `Vary: origin` that django-cors-headers stamps on every response is the
# second half of the problem. Cloudflare only varies its cache on
# Accept-Encoding; a response carrying any other Vary is commonly treated as
# uncacheable, which would leave images DYNAMIC even with Cache-Control set.
#
# Dropping it here is safe for images specifically: <img> tags are not
# CORS-controlled, so nothing in the SPA or the Capacitor webview relies on
# this header to display media. It would matter for a fetch()/canvas read of an
# image, which this app does not do.
_media_prefix = settings.MEDIA_URL.lstrip("/")
_media_max_age = int(os.getenv("MEDIA_CACHE_SECONDS", 60 * 60 * 24 * 30))  # 30 days


def _cacheable_media(request, *args, **kwargs):
    response = serve_media(request, *args, **kwargs)
    response.headers.pop("Vary", None)
    return response


_cached_media = cache_control(public=True, max_age=_media_max_age)(_cacheable_media)

urlpatterns += [
    re_path(rf"^{_media_prefix}(?P<path>.*)$", _cached_media, {"document_root": settings.MEDIA_ROOT}),
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
