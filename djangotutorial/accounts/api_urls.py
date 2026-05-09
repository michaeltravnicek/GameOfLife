from django.urls import path

from . import api_views

urlpatterns = [
    path("me/", api_views.me_view, name="api-me"),
    path("login/", api_views.login_api, name="api-login"),
    path("logout/", api_views.logout_api, name="api-logout"),
    path("register/", api_views.register_api, name="api-register"),
    path("profile/<str:username>/", api_views.profile_view, name="api-profile"),
]
