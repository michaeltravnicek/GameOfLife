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

from leaderboard import views as legacy_views
from . import views as react_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # JSON API for the React frontend
    path("api/", include("leaderboard.api_urls")),
    path("api/auth/", include("accounts.api_urls")),

    # Legacy JSON helpers retained until React wires them
    path("api/photos/<int:photo_id>/like/", legacy_views.toggle_photo_like_view, name="photo_like"),
    path("api/profile/<str:username>/monthly-points/", legacy_views.profile_monthly_points_api, name="profile-monthly-points"),

    # Django's built-in password-reset confirm/complete pages are still
    # server-rendered. The React SPA owns the "forgot password" form at
    # /zapomenute-heslo (POSTs to /api/auth/password-reset/); the email
    # link then lands users on these Django pages to set a new password.
    path("accounts/", include("accounts.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]

# React catch-all: must come last so /api/*, /admin/*, /accounts/* match first.
urlpatterns += [
    re_path(r"^(?!api/|admin/|media/|static/|accounts/).*$", react_views.react_index, name="react-index"),
]
