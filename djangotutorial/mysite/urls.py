"""URL configuration for mysite project.

The frontend is a React SPA. Django serves:
  - /admin/   Django admin (staff/superuser only)
  - /api/     DRF JSON endpoints consumed by React
  - /media/   user-uploaded files (via WhiteNoise/dev static)
  - /static/  built static assets
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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# React catch-all: must come last so /api/* and /admin/* are matched first.
urlpatterns += [
    re_path(r"^(?!api/|admin/|media/|static/).*$", react_views.react_index, name="react-index"),
]
