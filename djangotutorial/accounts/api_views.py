from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User as AuthUser
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from leaderboard.models import (
    EventFeedback,
    User as LeaderboardUser,
    UserToEvent,
)

from .forms import CustomUserCreationForm, parse_phone_number
from .models import Profile


def _serialize_user(user):
    if user is None or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    photo_url = None
    if profile and profile.photo:
        photo_url = profile.photo.url
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name() or user.username,
        "is_staff": user.is_staff,
        "role": profile.role if profile else "",
        "photo": photo_url,
        "instagram": profile.instagram if profile else "",
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    if not request.user.is_authenticated:
        return Response({"user": None})
    return Response({"user": _serialize_user(request.user)})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_api(request):
    identifier = (request.data.get("identifier") or request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    if not identifier or not password:
        return Response({"error": "Vyplň přihlašovací údaje."}, status=400)

    username = None
    phone = parse_phone_number(identifier)
    if phone is not None:
        try:
            lb_user = LeaderboardUser.objects.get(number=phone)
            profile = getattr(lb_user, "profile", None)
            if profile is not None:
                username = profile.user.username
        except LeaderboardUser.DoesNotExist:
            pass
    if username is None and AuthUser.objects.filter(username=identifier).exists():
        username = identifier
    # Also try email as username
    if username is None:
        candidate = AuthUser.objects.filter(email__iexact=identifier).first()
        if candidate:
            username = candidate.username

    if username is None:
        return Response({"error": "Uživatel nenalezen."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "Nesprávné heslo."}, status=400)
    if not user.is_active:
        return Response({"error": "Účet je deaktivovaný."}, status=400)

    login(request, user)
    return Response({"user": _serialize_user(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    logout(request)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def register_api(request):
    form = CustomUserCreationForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=400)
    user = form.save()
    login(request, user)
    return Response({"user": _serialize_user(user)})


@api_view(["GET"])
@permission_classes([AllowAny])
def profile_view(request, username):
    profile_user = get_object_or_404(AuthUser, username=username)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None

    total_points = 0
    total_events = 0
    past_events = []
    upcoming_rsvps = []
    rank = None

    if lb_user:
        agg = UserToEvent.objects.filter(user=lb_user).aggregate(
            total_points=Sum("points"),
            total_events=Count("id"),
        )
        total_points = agg["total_points"] or 0
        total_events = agg["total_events"] or 0

        past_qs = (
            UserToEvent.objects.filter(user=lb_user)
            .select_related("event").order_by("-event__date")[:50]
        )
        for ute in past_qs:
            ev = ute.event
            past_events.append({
                "slug": ev.slug,
                "name": ev.name,
                "date": ev.date,
                "place": ev.place,
                "points": ute.points,
            })

        if total_points > 0:
            rank = (
                LeaderboardUser.objects
                .annotate(tp=Coalesce(Sum("usertoevent__points"), 0))
                .filter(tp__gt=total_points).count()
            ) + 1

    if profile:
        rsvp_qs = (
            profile_user.rsvps.select_related("event")
            .filter(event__date__gte=timezone.now())
            .order_by("event__date")
        )
        for r in rsvp_qs:
            ev = r.event
            upcoming_rsvps.append({
                "slug": ev.slug,
                "name": ev.name,
                "date": ev.date,
                "place": ev.place,
                "points": ev.points,
            })

    photo_url = None
    if profile and profile.photo:
        photo_url = request.build_absolute_uri(profile.photo.url)

    return Response({
        "username": profile_user.username,
        "first_name": profile_user.first_name,
        "full_name": profile_user.get_full_name() or profile_user.username,
        "photo": photo_url,
        "instagram": profile.instagram if profile else "",
        "total_points": total_points,
        "total_events": total_events,
        "rank": rank,
        "past_events": past_events,
        "upcoming_rsvps": upcoming_rsvps,
        "is_own_profile": request.user.is_authenticated and request.user == profile_user,
    })
