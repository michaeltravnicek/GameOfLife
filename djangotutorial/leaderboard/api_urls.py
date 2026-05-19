from django.urls import path

from . import api_views

urlpatterns = [
    path("home/", api_views.home_view, name="api-home"),
    path("events/", api_views.events_list, name="api-events-list"),
    path("events/<slug:slug>/", api_views.event_detail, name="api-event-detail"),
    path("events/<slug:slug>/rsvp/", api_views.event_rsvp_toggle, name="api-event-rsvp"),
    path("events/<slug:slug>/feedback/", api_views.event_feedback, name="api-event-feedback"),
    path("events/<slug:slug>/checkin/", api_views.event_checkin, name="api-event-checkin"),
    path("leaderboard/", api_views.leaderboard_view, name="api-leaderboard"),
    path("gallery/", api_views.gallery_view, name="api-gallery"),
]
