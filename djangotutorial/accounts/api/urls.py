from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.me_view, name="api-me"),
    path("me/delete/", views.delete_me, name="api-delete-me"),
    path("login/", views.login_api, name="api-login"),
    path("logout/", views.logout_api, name="api-logout"),
    path("register/", views.register_api, name="api-register"),
    path("password-reset/", views.password_reset_api, name="api-password-reset"),
    path("password-reset/confirm/", views.password_reset_confirm_api, name="api-password-reset-confirm"),
    path("profile/photo/", views.profile_photo_upload, name="api-profile-photo"),
    path("profile/update/", views.profile_update, name="api-profile-update"),
]
