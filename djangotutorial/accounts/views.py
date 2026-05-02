from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as tz
from django.views.decorators.http import require_http_methods

from leaderboard.models import EventFeedback, ProfileAnswer, ProfileQuestion, Season, User as LeaderboardUser, UserToEvent

from .forms import CustomUserCreationForm, PhoneOrUsernameLoginForm, ProfileEditForm
from .models import Profile


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
        past_events_qs = (
            UserToEvent.objects.filter(user=lb_user)
            .select_related("event")
            .order_by("-event__date")[:20]
        )
        feedback_map = {
            fb.event_id: fb
            for fb in EventFeedback.objects.filter(
                auth_user=profile_user,
                event__in=[ute.event_id for ute in past_events_qs],
            )
        }
        past_events = []
        for ute in past_events_qs:
            ute.feedback = feedback_map.get(ute.event_id)
            past_events.append(ute)

    upcoming_rsvps = (
        profile_user.rsvps.select_related("event").order_by("event__date")
        if profile else []
    )

    profile_answers = {}
    if profile:
        profile_answers = {
            pa.question_id: pa
            for pa in ProfileAnswer.objects.filter(auth_user=profile_user)
            .select_related("question")
        }
        # Attach question objects to each answer so template can access question.text
        questions_with_answers = [
            {"question": q, "answer": profile_answers.get(q.id)}
            for q in ProfileQuestion.objects.all()
            if q.id in profile_answers and profile_answers[q.id].answer
        ]
        upcoming_rsvps = [rsvp for rsvp in upcoming_rsvps if rsvp.event.date >= tz.now()]

    # Rank in total leaderboard
    rank = None
    if lb_user is not None and total_points > 0:
        rank = (
            LeaderboardUser.objects
            .annotate(tp=Coalesce(Sum("usertoevent__points"), 0))
            .filter(tp__gt=total_points)
            .count()
        ) + 1

    all_seasons = list(Season.objects.all().order_by("-start_date"))

    context = {
        "profile_user": profile_user,
        "profile": profile,
        "is_own_profile": request.user == profile_user,
        "total_points": total_points,
        "total_events": total_events,
        "upcoming_rsvps": upcoming_rsvps,
        "past_events": past_events,
        "questions_with_answers": questions_with_answers if profile else [],
        "rank": rank,
        "all_seasons": all_seasons,
    }
    return render(request, "accounts/profile.html", context)


def attended_events_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None
    past_events = []
    if lb_user is not None:
        past_events = (
            UserToEvent.objects.filter(user=lb_user)
            .select_related("event")
            .order_by("-event__date")
        )
    return render(request, "accounts/attended_events.html", {
        "profile_user": profile_user,
        "past_events": past_events,
    })


@login_required
def my_profile_redirect(request):
    return redirect("profile", username=request.user.username)


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    # Auto-create Profile for users created outside the registration form
    # (e.g., superusers, legacy accounts from before the Profile model existed).
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil aktualizován!")
            return redirect("profile", username=request.user.username)
    else:
        initial = {
            "instagram": profile.instagram,
        }
        for answer in ProfileAnswer.objects.filter(auth_user=request.user):
            initial[f"question_{answer.question_id}"] = answer.answer
        form = ProfileEditForm(initial=initial, user=request.user)

    return render(request, "accounts/profile_edit.html", {"form": form})
