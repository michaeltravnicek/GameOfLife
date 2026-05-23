from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm
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
    Season,
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

    # "Remember me": persist the session for 30 days. Otherwise expire when
    # the browser closes (default behavior, but we set it explicitly so the
    # session age doesn't carry over from a previous "remember" login).
    remember = bool(request.data.get("remember", False))
    if remember:
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
    else:
        request.session.set_expiry(0)  # 0 = on browser close

    return Response({"user": _serialize_user(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    logout(request)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_api(request):
    """Trigger Django's standard password reset email flow.

    Always returns 200 OK with a generic message — we never disclose whether
    an email address is registered (avoids account enumeration).
    """
    email = (request.data.get("email") or "").strip()
    if not email:
        return Response({"error": "Zadej e-mail."}, status=400)

    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        )
    # Generic response regardless of whether email is in the DB.
    return Response({
        "ok": True,
        "message": "Pokud k tomuto e-mailu existuje účet, odeslali jsme odkaz pro reset hesla.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def register_api(request):
    form = CustomUserCreationForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=400)
    user = form.save()
    login(request, user)
    return Response({"user": _serialize_user(user)})


def _build_seasons(lb_user):
    seasons = Season.objects.all()
    result = []
    for s in seasons:
        utes = (
            UserToEvent.objects
            .filter(user=lb_user,
                    event__date__date__gte=s.start_date,
                    event__date__date__lte=s.end_date)
            .select_related("event", "event__category")
            .order_by("event__date")
        )
        season_pts = sum(u.points for u in utes)
        rank = None
        if season_pts > 0:
            rank = (
                UserToEvent.objects
                .filter(event__date__date__gte=s.start_date,
                        event__date__date__lte=s.end_date)
                .values("user")
                .annotate(pts=Sum("points"))
                .filter(pts__gt=season_pts)
                .count()
            ) + 1
        result.append({
            "label":      s.name,
            "start":      s.start_date,
            "end":        s.end_date,
            "is_active":  s.is_active,
            "season_pts": season_pts,
            "rank":       rank,
            "events": [
                {
                    "slug":     u.event.slug,
                    "name":     u.event.name,
                    "place":    u.event.place,
                    "date":     u.event.date,
                    "pts":      u.points,
                    "category": {"id": u.event.category.id, "name": u.event.category.name}
                                if u.event.category else None,
                }
                for u in utes
            ],
        })
    return result


@api_view(["GET"])
@permission_classes([AllowAny])
def profile_view(request, username):
    profile_user = get_object_or_404(AuthUser, username=username)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None

    total_points = 0
    total_events = 0
    upcoming_rsvps = []
    rank = None

    if lb_user:
        agg = UserToEvent.objects.filter(user=lb_user).aggregate(
            total_points=Sum("points"),
            total_events=Count("id"),
        )
        total_points = agg["total_points"] or 0
        total_events = agg["total_events"] or 0

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

    fav_cats = []
    if profile:
        fav_cats = [
            {"id": c.id, "name": c.name}
            for c in profile.favourite_categories.all()
        ]

    return Response({
        "username":   profile_user.username,
        "first_name": profile_user.first_name,
        "full_name":  profile_user.get_full_name() or profile_user.username,
        "photo":      photo_url,
        "bio":        profile.bio if profile else "",
        "city":       profile.city if profile else "",
        "since":      profile_user.date_joined.strftime("%Y-%m"),
        "instagram":  profile.instagram if profile else "",
        "strava":     profile.strava if profile else "",
        "spotify":    profile.spotify if profile else "",
        "tiktok":     profile.tiktok if profile else "",
        "favourite_categories": fav_cats,
        "privacy": {
            "hide_pts":    profile.hide_pts if profile else False,
            "hide_events": profile.hide_events if profile else False,
            "members_only":profile.members_only if profile else False,
        },
        "total_points":  total_points,
        "total_events":  total_events,
        "rank":          rank,
        "upcoming_rsvps": upcoming_rsvps,
        "seasons":       _build_seasons(lb_user) if lb_user else [],
        "is_own_profile": request.user.is_authenticated and request.user == profile_user,
    })


@api_view(["PATCH", "POST"])
@permission_classes([IsAuthenticated])
def profile_update(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    data = request.data

    if "first_name" in data:
        user.first_name = data["first_name"]
    if "last_name" in data:
        user.last_name = data["last_name"]
    if "email" in data:
        user.email = data["email"]
    new_handle = (data.get("username") or "").strip()
    if new_handle and new_handle != user.username:
        if AuthUser.objects.filter(username=new_handle).exclude(pk=user.pk).exists():
            return Response({"error": "Přezdívka je obsazena."}, status=400)
        user.username = new_handle
    user.save()

    for field in ("bio", "city", "instagram", "strava", "spotify", "tiktok"):
        if field in data:
            setattr(profile, field, data[field])

    if "favourite_categories" in data:
        raw = data.getlist("favourite_categories") if hasattr(data, "getlist") else data["favourite_categories"]
        if not isinstance(raw, list):
            raw = [raw]
        from leaderboard.models import Category
        cats = list(Category.objects.filter(id__in=[int(x) for x in raw if str(x).isdigit()])[:3])
        profile.save()
        profile.favourite_categories.set(cats)
    else:
        profile.save()

    for flag in ("hide_pts", "hide_events", "members_only"):
        if flag in data:
            setattr(profile, flag, str(data[flag]).lower() in ("1", "true"))
    profile.save(update_fields=["hide_pts", "hide_events", "members_only"])

    if "photo" in request.FILES:
        profile.photo = request.FILES["photo"]
        profile.save(update_fields=["photo"])
    elif data.get("remove_photo"):
        profile.photo = None
        profile.save(update_fields=["photo"])

    return Response({"ok": True, "user": _serialize_user(user)})
