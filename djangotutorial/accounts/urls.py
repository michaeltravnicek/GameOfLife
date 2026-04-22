from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("prihlasit/", views.login_view, name="login"),
    path("registrace/", views.register_view, name="register"),
    path("odhlasit/", views.logout_view, name="logout"),
    path("profil/", views.my_profile_redirect, name="my_profile"),
    path("profil/upravit/", views.profile_edit_view, name="profile_edit"),
    path("profil/<str:username>/", views.public_profile_view, name="profile"),

    # Password reset flow
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/password_reset_email.html",
        subject_template_name="accounts/password_reset_subject.txt",
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
    ), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
