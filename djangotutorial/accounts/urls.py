from django.urls import path

from . import views

urlpatterns = [
    path("prihlasit/", views.login_view, name="login"),
    path("registrace/", views.register_view, name="register"),
    path("odhlasit/", views.logout_view, name="logout"),
    path("profil/", views.my_profile_redirect, name="my_profile"),
    path("profil/<str:username>/", views.public_profile_view, name="profile"),
]
