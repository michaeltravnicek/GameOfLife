"""Serializers for the auth/profile API.

These document the request and response shapes for drf-spectacular (Swagger).
The views still parse input via Django forms / manual access, so these are the
schema contract rather than the runtime parser — keep them in sync with the
payloads built in accounts.services.
"""
from rest_framework import serializers

# Privacy flags are stored and returned, but no code hides anything based on
# them yet. Surfaced in the schema so API consumers don't assume they work.
_NOT_ENFORCED_NOTE = (
    "NOT ENFORCED YET — the value is stored and echoed back, but nothing is "
    "actually hidden based on it."
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
    identifier = serializers.CharField(help_text="Phone number, username or e-mail.")
    password = serializers.CharField(style={"input_type": "password"})
    remember = serializers.BooleanField(
        required=False, default=False,
        help_text="Keep the session for 30 days instead of until browser close.")
    client = serializers.ChoiceField(
        choices=["mobile"], required=False,
        help_text="Send 'mobile' to also receive a token for native apps.")


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
    client = serializers.ChoiceField(choices=["mobile"], required=False)


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
    hide_pts = serializers.BooleanField(
        required=False, help_text=_NOT_ENFORCED_NOTE + " Also has no UI toggle yet.")
    hide_events = serializers.BooleanField(required=False, help_text=_NOT_ENFORCED_NOTE)
    members_only = serializers.BooleanField(required=False, help_text=_NOT_ENFORCED_NOTE)
    favourite_categories = serializers.ListField(
        child=serializers.IntegerField(), required=False,
        help_text="Up to 3 category ids (extras are ignored).")
    photo = serializers.ImageField(required=False)
    remove_photo = serializers.BooleanField(required=False, help_text="Clear the current avatar.")


# --- Responses ---

class LoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    token = serializers.CharField(required=False, help_text="Present only when client=mobile.")


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
    """Stored privacy preferences. See the per-field note: none are enforced yet,
    so a client must NOT assume hidden data is actually withheld."""
    hide_pts = serializers.BooleanField(help_text=_NOT_ENFORCED_NOTE)
    hide_events = serializers.BooleanField(help_text=_NOT_ENFORCED_NOTE)
    members_only = serializers.BooleanField(help_text=_NOT_ENFORCED_NOTE)


class ProfileSerializer(serializers.Serializer):
    """Public profile core (accounts.services.profile_payload).

    `last_name` and `email` are present only when viewing your own profile.
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
    privacy = _ProfilePrivacySerializer()
    total_points = serializers.IntegerField()
    total_events = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    upcoming_rsvps = _ProfileUpcomingRsvpSerializer(many=True)
    past_events = _ProfilePastEventSerializer(many=True)
    seasons = _ProfileSeasonSummarySerializer(many=True)
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
