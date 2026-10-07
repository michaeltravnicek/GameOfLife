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
import re

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control
from django.views.static import serve as serve_media

from accounts.views import social_signup_unavailable

from . import views as react_views
from .sitemaps import SITEMAPS

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),

    # Crawler-facing files. Must be declared before the React catch-all, which
    # would otherwise serve the SPA shell for these paths.
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", react_views.robots_txt, name="robots"),

    # Health check. Point Render's health-check path here — the default (`/`)
    # returns the SPA shell from memory and answers 200 with the DB down.
    path("healthz/", react_views.healthz, name="healthz"),

    # Deliberate 500 for verifying the Sentry pipeline. Superuser-only —
    # see the view's docstring for why it isn't the open route Sentry suggests.
    path("sentry-debug/", react_views.sentry_debug, name="sentry-debug"),

    # Proxy-chain diagnostic (superuser only) — used to confirm PROXY_COUNT
    # matches reality, since getting it wrong silently breaks rate limiting.
    path("whoami/", react_views.whoami, name="whoami"),

    # JSON API for the React frontend. Versioned so installed mobile app
    # builds can keep calling v1 after the contract changes (a future v2
    # mounts alongside; v1 routes stay until no clients use them).
    # Social login (Google). Full-page server routes, never React Router links —
    # a client-side <Link> here would 404 inside the SPA instead of redirecting
    # to Google. Reserved from the catch-all below via _reserved.
    # Ahead of allauth's own route: its social signup form is a dead end here.
    path("accounts/3rdparty/signup/", social_signup_unavailable),
    path("accounts/", include("allauth.urls")),

    path("api/v1/", include("leaderboard.api.urls")),
    path("api/v1/auth/", include("accounts.api.urls")),
    path("api/v1/profiles/", include("accounts.api.profiles_urls")),
]

# Serve user-uploaded media from local disk. `static()` does nothing when
# DEBUG=False and WhiteNoise serves only STATIC_ROOT, so this route exists in
# every environment; with R2 enabled the storage backend hands out CDN URLs and
# it is only hit during a cutover. Public + cacheable because filenames are
# effectively immutable (Django appends a random suffix on collision); the
# `immutable` directive is left off so a mistake can still be corrected within
# a month.
_media_prefix = settings.MEDIA_URL.lstrip("/")
_media_max_age = int(os.getenv("MEDIA_CACHE_SECONDS", 60 * 60 * 24 * 30))  # 30 days
_cached_media = cache_control(public=True, max_age=_media_max_age)(serve_media)

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

# React catch-all: must come last so /api/*, the admin, /media/*, /static/* match
# first. The (/|$) lets us also reserve the bare prefixes (e.g. /admin with no
# trailing slash) for Django — otherwise React would serve them and show a blank
# screen.
#
# The admin segment is read from settings rather than hardcoded: with a custom
# ADMIN_URL a literal "admin" here would let the SPA swallow the real admin path
# and serve a blank page instead of the login form.
_admin_segment = re.escape(settings.ADMIN_URL.strip("/").split("/")[0])
_reserved = "|".join(["api", _admin_segment, "media", "static", "accounts", "healthz"])
urlpatterns += [
    re_path(rf"^(?!(?:{_reserved})(?:/|$)).*$", react_views.react_index, name="react-index"),
]

# Unknown /api/ paths answer in JSON instead of an HTML error page — the SPA
# parses every API response as JSON, so HTML there surfaces as a parse failure
# rather than "not found". Everything else still falls through to the SPA.
handler404 = "mysite.views.api_not_found"
