"""Serializers for the auth/profile API.

These document the request and response shapes for drf-spectacular (Swagger).
The views still parse input via Django forms / manual access, so these are the
schema contract rather than the runtime parser — keep them in sync with the
payloads built in accounts.services.
"""
from rest_framework import serializers

# Privacy flags are enforced server-side by leaderboard.privacy.visibility_for.
_PRIVACY_NOTE = (
    "Enforced server-side: hidden sections are omitted from profile/player "
    "payloads and their season sub-resources, and a members-only profile 404s "
    "for anonymous callers. The owner and admins always see everything."
)


class UserSerializer(serializers.Serializer):
    """The current-user object returned by /me, login and register.

    Mirrors accounts.services.serialize_user.
    """
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.CharField()
    is_staff = serializers.BooleanField()
    role = serializers.CharField(allow_blank=True, help_text='"", "close", "photographer" or "admin".')
    photo = serializers.URLField(allow_null=True)
    instagram = serializers.CharField(allow_blank=True)


# --- Requests ---

class LoginRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Username or e-mail.")
    password = serializers.CharField(style={"input_type": "password"})
    remember = serializers.BooleanField(
        required=False, default=False,
        help_text="Keep the session for 30 days instead of until browser close.")


class RegisterRequestSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    username = serializers.CharField(help_text="Public display handle.")
    email = serializers.EmailField()
    password1 = serializers.CharField(style={"input_type": "password"})
    password2 = serializers.CharField(style={"input_type": "password"}, help_text="Must match password1.")
    gdpr_consent = serializers.BooleanField(
        help_text="Must be true. Records agreement to the privacy policy; the "
                  "server stores the timestamp and policy version.",
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(help_text="From the reset link e-mail.")
    token = serializers.CharField(help_text="From the reset link e-mail.")
    new_password = serializers.CharField(style={"input_type": "password"})


class ProfilePhotoUploadRequestSerializer(serializers.Serializer):
    photo = serializers.ImageField()


class ProfileUpdateRequestSerializer(serializers.Serializer):
    """All fields optional — send only what changes (accepted as multipart)."""
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, help_text="New handle; 400 if already taken.")
    bio = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    instagram = serializers.CharField(required=False, allow_blank=True)
    strava = serializers.CharField(required=False, allow_blank=True)
    spotify = serializers.CharField(required=False, allow_blank=True)
    tiktok = serializers.CharField(required=False, allow_blank=True)
    hide_pts = serializers.BooleanField(required=False, help_text=_PRIVACY_NOTE)
    hide_events = serializers.BooleanField(required=False, help_text=_PRIVACY_NOTE)
    members_only = serializers.BooleanField(required=False, help_text=_PRIVACY_NOTE)
    favourite_categories = serializers.ListField(
        child=serializers.IntegerField(), required=False,
        help_text="Up to 3 category ids (extras are ignored).")
    photo = serializers.ImageField(required=False)
    remove_photo = serializers.BooleanField(required=False, help_text="Clear the current avatar.")


# --- Responses ---

class LoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()


class MeResponseSerializer(serializers.Serializer):
    user = UserSerializer(allow_null=True, help_text="null for anonymous callers.")


class OkResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class MessageResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()


class ProfileMutationResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    user = UserSerializer()


class _CategoryRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class _ProfileSeasonSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField()
    is_active = serializers.BooleanField()
    season_pts = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)


class _ProfileUpcomingRsvpSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    date = serializers.DateTimeField()
    place = serializers.CharField()
    points = serializers.IntegerField()
    survey_url = serializers.CharField(allow_blank=True)


class _ProfilePastEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    date = serializers.DateTimeField()
    place = serializers.CharField()
    points = serializers.IntegerField()
    logo = serializers.URLField(allow_null=True)


class _ProfilePrivacySerializer(serializers.Serializer):
    """The owner's own privacy preferences. Returned only on your own profile --
    which switches someone else flipped is not a visitor's business."""
    hide_pts = serializers.BooleanField(help_text=_PRIVACY_NOTE)
    hide_events = serializers.BooleanField(help_text=_PRIVACY_NOTE)
    members_only = serializers.BooleanField(help_text=_PRIVACY_NOTE)


class ProfileSerializer(serializers.Serializer):
    """Public profile core (accounts.services.profile_payload).

    `last_name`, `email` and `privacy` are present only when viewing your own
    profile.

    Privacy-gated sections are **omitted, not zeroed**: when the owner sets
    `hide_pts` the payload has no `total_points`/`total_events`/`rank` at all,
    and `hide_events` removes `upcoming_rsvps`/`past_events`/`seasons`. Read
    `hidden` to tell "withheld" from "genuinely none" -- defaulting a missing
    total to 0 would display a real player as having scored nothing.
    """
    username = serializers.CharField()
    first_name = serializers.CharField()
    full_name = serializers.CharField()
    photo = serializers.URLField(allow_null=True)
    bio = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)
    since = serializers.CharField(help_text='First-event month, e.g. "2024-05".')
    instagram = serializers.CharField(allow_blank=True)
    strava = serializers.CharField(allow_blank=True)
    spotify = serializers.CharField(allow_blank=True)
    tiktok = serializers.CharField(allow_blank=True)
    favourite_categories = _CategoryRefSerializer(many=True)
    hidden = serializers.ListField(
        child=serializers.ChoiceField(choices=["points", "events"]),
        help_text='Sections withheld by the owner\'s privacy flags, e.g. ["points"].')
    privacy = _ProfilePrivacySerializer(required=False)
    total_points = serializers.IntegerField(required=False)
    total_events = serializers.IntegerField(required=False)
    rank = serializers.IntegerField(allow_null=True, required=False)
    upcoming_rsvps = _ProfileUpcomingRsvpSerializer(many=True, required=False)
    past_events = _ProfilePastEventSerializer(many=True, required=False)
    seasons = _ProfileSeasonSummarySerializer(many=True, required=False)
    is_own_profile = serializers.BooleanField()
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)


class SeasonEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    place = serializers.CharField()
    date = serializers.DateTimeField()
    pts = serializers.IntegerField()
    category = _CategoryRefSerializer(allow_null=True)


class SeasonDetailSerializer(serializers.Serializer):
    """One season's breakdown for a player (accounts.services.season_detail)."""
    id = serializers.IntegerField()
    label = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField()
    is_active = serializers.BooleanField()
    season_pts = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    events = SeasonEventSerializer(many=True)
