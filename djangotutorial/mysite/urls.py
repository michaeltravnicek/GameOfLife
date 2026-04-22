"""URL configuration for mysite project."""
from django.conf import settings
from django.conf.urls.static import serve, static
from django.contrib import admin
from django.urls import include, path, re_path

from leaderboard import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.home_view, name="home"),

    # Czech routes (primary)
    path("events/", views.events_view, name="events"),
    path("events/<slug:slug>/", views.event_detail_view, name="event_detail"),
    path("events/<slug:slug>/rsvp/", views.event_rsvp_view, name="event_rsvp"),
    path("events/<slug:slug>/feedback/", views.event_feedback_view, name="event_feedback"),
    path("leaderboard/", views.leaderboard_view, name="leaderboard"),
    path("o-bodech/", views.about_points_view, name="about_points"),

    # Auth (mounted at root so /prihlasit/, /registrace/, /profil/<username>/ work)
    path("", include("accounts.urls")),

    # API
    path("api/user/<int:user_id>/", views.user_detail_view, name="user-detail"),
    path("api/events/<str:event_id>/images/", views.events_image_views, name="images"),

    re_path(r"^media(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
