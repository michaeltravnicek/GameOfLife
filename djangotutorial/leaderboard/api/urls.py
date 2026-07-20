from django.urls import path

from . import views

urlpatterns = [
    path("stats/", views.stats_view, name="api-stats"),
    path("hero/", views.hero_view, name="api-hero"),
    path("checkin-events/", views.checkin_events_view, name="api-checkin-events"),
    path("events/create/", views.event_create, name="api-event-create"),
    path("events/", views.events_list, name="api-events-list"),
    path("events/<slug:slug>/", views.event_detail, name="api-event-detail"),
    path("events/<slug:slug>/update/", views.event_update, name="api-event-update"),
    path("events/<slug:slug>/delete/", views.event_delete, name="api-event-delete"),
    path("events/<slug:slug>/rsvp/", views.event_rsvp, name="api-event-rsvp"),
    path("events/<slug:slug>/rsvps/", views.event_rsvps, name="api-event-rsvps"),
    path("events/<slug:slug>/attendees/", views.event_attendees, name="api-event-attendees"),
    path("events/<slug:slug>/attendees/<int:user_id>/", views.event_attendee_detail,
         name="api-event-attendee"),
    path("events/<slug:slug>/feedback/", views.event_feedback, name="api-event-feedback"),
    path("events/<slug:slug>/checkin/", views.event_checkin, name="api-event-checkin"),
    path("events/<slug:slug>/images/", views.event_images_upload, name="api-event-images"),
    path("leaderboard/", views.leaderboard_view, name="api-leaderboard"),
    path("seasons/", views.seasons_list, name="api-seasons"),
    path("players/<int:user_id>/", views.player_detail, name="api-player"),
    path("players/<int:user_id>/seasons/<int:season_id>/", views.player_season_detail, name="api-player-season"),
    path("gallery/", views.gallery_view, name="api-gallery"),
    path("categories/", views.categories_list, name="api-categories"),
    path("photos/", views.photo_upload, name="api-photo-upload"),
    path("photos/<int:photo_id>/like/", views.photo_like, name="api-photo-like"),
    path("admin/feedbacks/", views.admin_feedbacks, name="api-admin-feedbacks"),
]
