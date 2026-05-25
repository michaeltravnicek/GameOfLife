from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User as AuthUser
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from leaderboard.models import Season

from accounts.forms import CustomUserCreationForm
from accounts.services import (
    profile_payload,
    reset_password,
    resolve_login_username,
    season_detail,
    serialize_user,
    set_profile_photo,
    update_profile,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    """Current authenticated user (or `{user: null}` for guests)."""
    user = request.user if request.user.is_authenticated else None
    return Response({"user": serialize_user(user, request)}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_api(request):
    """Log in via phone / username / email + password. Optional `remember`."""
    identifier = (request.data.get("identifier") or request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    if not identifier or not password:
        return Response({"error": "Vyplň přihlašovací údaje."}, status=status.HTTP_400_BAD_REQUEST)

    username = resolve_login_username(identifier)
    if username is None:
        return Response({"error": "Uživatel nenalezen."}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "Nesprávné heslo."}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        return Response({"error": "Účet je deaktivovaný."}, status=status.HTTP_400_BAD_REQUEST)

    login(request, user)
    # "Remember me" → 30-day session; otherwise expire on browser close.
    remember = bool(request.data.get("remember", False))
    request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
    return Response({"user": serialize_user(user, request)}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    """Log out the current session."""
    logout(request)
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_api(request):
    """Trigger Django's password-reset email. Generic 200 (no account enumeration)."""
    email = (request.data.get("email") or "").strip()
    if not email:
        return Response({"error": "Zadej e-mail."}, status=status.HTTP_400_BAD_REQUEST)

    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        )
    return Response({
        "ok": True,
        "message": "Pokud k tomuto e-mailu existuje účet, odeslali jsme odkaz pro reset hesla.",
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_api(request):
    """Set a new password from the email's uid+token. Body: {uid, token, new_password}.

    The React page at /obnova-hesla/<uid>/<token>/ POSTs here.
    """
    ok, error = reset_password(
        request.data.get("uid") or "",
        request.data.get("token") or "",
        request.data.get("new_password") or "",
    )
    if not ok:
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def register_api(request):
    """Create an account (links to a leaderboard user by phone) and log in."""
    form = CustomUserCreationForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    user = form.save()
    login(request, user)
    return Response({"user": serialize_user(user, request)}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def profile_view(request, username):
    """Public profile core: stats, rank, upcoming RSVPs, and season summaries.

    Per-season event detail is loaded lazily via `profile_season_view`.
    """
    profile_user = get_object_or_404(AuthUser, username=username)
    return Response(profile_payload(profile_user, request), status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def profile_season_view(request, username, season_id):
    """One season's events/points/rank for a user (lazy-loaded per profile tab)."""
    profile_user = get_object_or_404(AuthUser, username=username)
    season = get_object_or_404(Season, pk=season_id)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None
    return Response(season_detail(lb_user, season), status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_photo_upload(request):
    """Upload/replace the current user's avatar (downscaled to 400×400). Multipart: `photo`."""
    photo = request.FILES.get("photo")
    if not photo:
        return Response({"error": "Nahraj prosím fotku."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        set_profile_photo(request.user, photo)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True, "user": serialize_user(request.user, request)},
                    status=status.HTTP_200_OK)


@api_view(["PATCH", "POST"])
@permission_classes([IsAuthenticated])
def profile_update(request):
    """Update the current user's account + profile fields, photo, and favourite categories."""
    try:
        update_profile(request.user, request.data, request.FILES)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True, "user": serialize_user(request.user, request)},
                    status=status.HTTP_200_OK)
