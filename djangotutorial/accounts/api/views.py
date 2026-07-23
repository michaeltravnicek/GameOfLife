import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User as AuthUser
from django.db import transaction
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    MeResponseSerializer,
    MessageResponseSerializer,
    OkResponseSerializer,
    PasswordResetConfirmRequestSerializer,
    PasswordResetRequestSerializer,
    ProfileMutationResponseSerializer,
    ProfilePhotoUploadRequestSerializer,
    ProfileSerializer,
    ProfileUpdateRequestSerializer,
    RegisterRequestSerializer,
    SeasonDetailSerializer,
)
from .throttles import LoginThrottle, PasswordResetThrottle, RegisterThrottle

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


@extend_schema(tags=["Auth"], responses=MeResponseSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    """Current authenticated user (or `{user: null}` for guests)."""
    user = request.user if request.user.is_authenticated else None
    return Response({"user": serialize_user(user, request)}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth"],
    request=LoginRequestSerializer,
    responses=LoginResponseSerializer,
    examples=[
        OpenApiExample(
            "Web login",
            value={"identifier": "jan.novak@example.com", "password": "s3cret", "remember": True},
            request_only=True,
        ),
        OpenApiExample(
            "Mobile login (returns a token)",
            value={"identifier": "603123456", "password": "s3cret", "client": "mobile"},
            request_only=True,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_api(request):
    """Log in via phone / username / email + password. Optional `remember`.

    Bad credentials → one generic 401 for both unknown identifier and wrong
    password: distinct messages would let anyone probe which phone numbers /
    e-mails have an account (the password-reset endpoint hides this the same
    way). ModelBackend already refuses inactive users inside authenticate().
    """
    identifier = (request.data.get("identifier") or request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    if not identifier or not password:
        return Response({"error": "Vyplň přihlašovací údaje."}, status=status.HTTP_400_BAD_REQUEST)

    username = resolve_login_username(identifier)
    user = (authenticate(request, username=username, password=password)
            if username is not None else None)
    if user is None:
        return Response({"error": "Nesprávné přihlašovací údaje."},
                        status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    # "Remember me" → 30-day session; otherwise expire on browser close.
    remember = bool(request.data.get("remember", False))
    request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)

    payload = {"user": serialize_user(user, request)}
    # Native app can't rely on webview cookies; it authenticates with a DRF token.
    if request.data.get("client") == "mobile":
        with transaction.atomic():
            token, _ = Token.objects.get_or_create(user=user)
        payload["token"] = token.key
    return Response(payload, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"], request=None, responses=OkResponseSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    """Log out the current session. Revokes the mobile token when used."""
    if isinstance(request.auth, Token):
        with transaction.atomic():
            request.auth.delete()
    logout(request)
    return Response({"ok": True}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth"],
    request=PasswordResetRequestSerializer,
    responses=MessageResponseSerializer,
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_api(request):
    """Trigger Django's password-reset email. Generic 200 (no account enumeration)."""
    email = (request.data.get("email") or "").strip()
    if not email:
        return Response({"error": "Zadej e-mail."}, status=status.HTTP_400_BAD_REQUEST)

    form = PasswordResetForm({"email": email})
    if form.is_valid():
        try:
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="accounts/password_reset_email.html",
                subject_template_name="accounts/password_reset_subject.txt",
            )
        except Exception:
            logger.exception("Password reset email failed for %s", email)
    return Response({
        "ok": True,
        "message": "Pokud k tomuto e-mailu existuje účet, odeslali jsme odkaz pro reset hesla.",
    }, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth"],
    request=PasswordResetConfirmRequestSerializer,
    responses=OkResponseSerializer,
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
@transaction.atomic
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


@extend_schema(
    tags=["Auth"],
    request=RegisterRequestSerializer,
    responses=LoginResponseSerializer,
    examples=[
        OpenApiExample(
            "New account",
            value={
                "first_name": "Jan", "username": "jannovak",
                "email": "jan.novak@example.com", "phone": "603123456",
                "password1": "s3cret-pass", "password2": "s3cret-pass",
            },
            request_only=True,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
@transaction.atomic
def register_api(request):
    """Create an unlinked account, log in, and hint if points may already exist.

    No phone number: the account starts with no LeaderboardUser attached. If the
    name resembles an existing unclaimed player, the response carries a neutral
    `possible_link` flag so the UI can say "we may already have your points" —
    but the actual link is only ever made by an admin (matching.suggest_players
    is a ranking, never a write), because self-service claiming would let anyone
    inherit a namesake's history.
    """
    form = CustomUserCreationForm(request.data)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    user = form.save()
    # Explicit backend required: this user came from form.save(), not
    # authenticate(), so it carries no `.backend`, and with django-axes there is
    # more than one backend configured for login() to pick from.
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    # Deliberately a boolean, not the matched names/points: revealing which
    # player a stranger's name resembles would re-identify people who never
    # registered. The admin sees the candidates; the registrant sees only that
    # a link is likely coming.
    from accounts import matching
    possible_link = bool(
        matching.suggest_players(user, list(matching.unlinked_players()), limit=1)
    )

    payload = {"user": serialize_user(user, request), "possible_link": possible_link}
    if request.data.get("client") == "mobile":
        token, _ = Token.objects.get_or_create(user=user)
        payload["token"] = token.key
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Profile"], responses=ProfileSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def profile_view(request, username):
    """Public profile core: stats, rank, upcoming RSVPs, and season summaries.

    Per-season event detail is loaded lazily via `profile_season_view`.
    """
    profile_user = get_object_or_404(AuthUser, username=username)
    return Response(profile_payload(profile_user, request), status=status.HTTP_200_OK)


@extend_schema(tags=["Profile"], responses=SeasonDetailSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def profile_season_view(request, username, season_id):
    """One season's events/points/rank for a user (lazy-loaded per profile tab)."""
    profile_user = get_object_or_404(AuthUser, username=username)
    season = get_object_or_404(Season, pk=season_id)
    profile = getattr(profile_user, "profile", None)
    lb_user = profile.leaderboard_user if profile else None
    return Response(season_detail(lb_user, season), status=status.HTTP_200_OK)


@extend_schema(
    tags=["Profile"],
    request=ProfilePhotoUploadRequestSerializer,
    responses=ProfileMutationResponseSerializer,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_photo_upload(request):
    """Upload/replace the current user's avatar (downscaled to 400×400). Multipart: `photo`."""
    photo = request.FILES.get("photo")
    if not photo:
        return Response({"error": "Nahraj prosím fotku."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic():
            set_profile_photo(request.user, photo)
            payload = {"ok": True, "user": serialize_user(request.user, request)}
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Profile"],
    request=ProfileUpdateRequestSerializer,
    responses=ProfileMutationResponseSerializer,
)
@api_view(["PATCH", "POST"])
@permission_classes([IsAuthenticated])
def profile_update(request):
    """Update the current user's account + profile fields, photo, and favourite categories."""
    try:
        with transaction.atomic():
            update_profile(request.user, request.data, request.FILES)
            payload = {"ok": True, "user": serialize_user(request.user, request)}
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(payload, status=status.HTTP_200_OK)
