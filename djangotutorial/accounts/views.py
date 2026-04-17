from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from leaderboard.models import UserToEvent

from .forms import CustomUserCreationForm, PhoneOrUsernameLoginForm


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = PhoneOrUsernameLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Ahoj, {user.first_name or user.username}!")
            next_url = request.GET.get("next") or request.POST.get("next") or "home"
            return redirect(next_url)
    else:
        form = PhoneOrUsernameLoginForm(request)

    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Účet vytvořen. Vítej v Game of Yolo!")
            return redirect("home")
    else:
        form = CustomUserCreationForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    logout(request)
    messages.success(request, "Odhlášeno.")
    return redirect("home")


def public_profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None

    total_points = 0
    total_events = 0
    upcoming_rsvps = []
    past_events = []

    if lb_user is not None:
        agg = UserToEvent.objects.filter(user=lb_user).aggregate(
            total_points=Sum("points"),
            total_events=Count("id"),
        )
        total_points = agg["total_points"] or 0
        total_events = agg["total_events"] or 0
        past_events = (
            UserToEvent.objects.filter(user=lb_user)
            .select_related("event")
            .order_by("-event__date")[:20]
        )

    upcoming_rsvps = (
        profile_user.rsvps.select_related("event").order_by("event__date")
        if profile else []
    )

    context = {
        "profile_user": profile_user,
        "is_own_profile": request.user == profile_user,
        "total_points": total_points,
        "total_events": total_events,
        "upcoming_rsvps": upcoming_rsvps,
        "past_events": past_events,
    }
    return render(request, "accounts/profile.html", context)


@login_required
def my_profile_redirect(request):
    return redirect("profile", username=request.user.username)
