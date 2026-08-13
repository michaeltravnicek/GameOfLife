"""Public profile reads, mounted at /api/profiles/."""
from django.urls import path

from . import views

urlpatterns = [
    path("<str:username>/", views.profile_view, name="api-profile"),
    path("<str:username>/seasons/<int:season_id>/", views.profile_season_view,
         name="api-profile-season"),
]
