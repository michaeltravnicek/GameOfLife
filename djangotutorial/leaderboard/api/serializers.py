from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from leaderboard.image_utils import ALLOWED_IMAGE_CONTENT_TYPES, MAX_UPLOAD_BYTES, variant_url
from leaderboard.models import Category, Event, EventFeedback, EventRSVP, ImageToEvent, UserPhoto

# Logos may be SVG (vector) as well as raster — unlike the poster `image`, which
# is downscaled by Pillow on save and so must stay a raster format.
_ALLOWED_LOGO_CONTENT_TYPES = ALLOWED_IMAGE_CONTENT_TYPES | {"image/svg+xml"}


def validate_logo_file(uploaded):
    """Content-type + size guard for a logo upload — no Pillow decode, so SVG passes.

    ModelSerializer would otherwise map Event.logo to an ImageField that
    Pillow-verifies the file and rejects SVG.
    """
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if content_type and content_type not in _ALLOWED_LOGO_CONTENT_TYPES:
        raise serializers.ValidationError(
            "Logo musí být PNG, JPG, WEBP, GIF nebo SVG.")
    if (getattr(uploaded, "size", 0) or 0) > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError("Logo je příliš velké (max 15 MB).")


class UserPhotoOutSerializer(serializers.Serializer):
    """Shape of one community photo embedded in an event's `user_photos`."""
    url = serializers.URLField()
    uploaded_by = serializers.CharField()
    caption = serializers.CharField()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class EventListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "slug", "name", "description", "place",
            "date", "points", "image", "logo", "capacity", "is_past", "category",
            "visible_to_users", "visible_to_close",
        ]

    def get_image(self, obj) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_logo(self, obj) -> str | None:
        if not obj.logo:
            return None
        request = self.context.get("request")
        url = obj.logo.url
        return request.build_absolute_uri(url) if request else url

    def get_is_past(self, obj) -> bool:
        from django.utils import timezone
        return bool(obj.date and obj.date < timezone.now())


class EventDetailSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    image_mobile = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    rsvp_count = serializers.SerializerMethodField()
    attendee_count = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    has_rsvp = serializers.SerializerMethodField()
    has_attended = serializers.SerializerMethodField()
    feedback_given = serializers.SerializerMethodField()
    official_images = serializers.SerializerMethodField()
    user_photos = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "slug", "name", "description", "place", "date", "end_date",
            "points", "image", "image_mobile", "logo", "rules", "capacity",
            "latitude", "longitude", "category",
            "survey_url", "visible_to_users", "visible_to_close",
            "is_past", "rsvp_count", "attendee_count", "is_full", "has_rsvp",
            "has_attended", "feedback_given",
            "official_images", "user_photos",
        ]

    def _abs(self, image_field):
        if not image_field:
            return None
        request = self.context.get("request")
        url = image_field.url
        return request.build_absolute_uri(url) if request else url

    def get_image(self, obj) -> str | None:
        return self._abs(obj.image)

    def get_image_mobile(self, obj) -> str | None:
        return variant_url(obj.image, self.context.get("request"))

    def get_logo(self, obj) -> str | None:
        return self._abs(obj.logo)

    def get_is_past(self, obj) -> bool:
        from django.utils import timezone
        return bool(obj.date and obj.date < timezone.now())

    def _rsvp_count(self, obj):
        # Memoize per instance — rsvp_count + is_full both need it.
        if not hasattr(obj, "_cached_rsvp_count"):
            obj._cached_rsvp_count = obj.rsvps.count()
        return obj._cached_rsvp_count

    def get_rsvp_count(self, obj) -> int:
        return self._rsvp_count(obj)

    def get_attendee_count(self, obj) -> int:
        # Real attendance (UserToEvent), distinct from rsvp_count (intentions).
        from leaderboard.models import UserToEvent
        return UserToEvent.objects.filter(event=obj).count()

    def get_is_full(self, obj) -> bool:
        if obj.capacity is None:
            return False
        return self._rsvp_count(obj) >= obj.capacity

    def get_has_rsvp(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return EventRSVP.objects.filter(auth_user=request.user, event=obj).exists()

    def get_has_attended(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        from accounts.models import Profile
        from leaderboard.models import UserToEvent
        try:
            lb_user = request.user.profile.leaderboard_user
        except (AttributeError, Profile.DoesNotExist):
            return False
        if lb_user is None:
            return False
        return UserToEvent.objects.filter(user=lb_user, event=obj).exists()

    def get_feedback_given(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        from accounts.models import Profile  # local import — avoid app-load cycle

        try:
            lb_user = request.user.profile.leaderboard_user
        except (AttributeError, Profile.DoesNotExist):
            return False
        if lb_user is None:
            return False
        return EventFeedback.objects.filter(user=lb_user, event=obj).exists()

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_official_images(self, obj):
        request = self.context.get("request")
        return [
            request.build_absolute_uri(img.image.url) if request else img.image.url
            for img in ImageToEvent.objects.filter(event=obj)
            if img.image
        ]

    @extend_schema_field(UserPhotoOutSerializer(many=True))
    def get_user_photos(self, obj):
        request = self.context.get("request")
        return [
            {
                "url": request.build_absolute_uri(p.image.url) if request else p.image.url,
                "uploaded_by": p.auth_user.get_full_name() or p.auth_user.username,
                "caption": p.caption,
            }
            for p in UserPhoto.objects.filter(event=obj).select_related("auth_user")
            if p.image
        ]


class FeedbackSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=10)
    # default="" so an omitted comment still lands in validated_data — the view
    # feeds validated_data into update_or_create(defaults=...), and a missing
    # key there would silently keep the old comment instead of clearing it.
    comment = serializers.CharField(max_length=1000, allow_blank=True, default="")


class CheckinSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class PhotoUploadSerializer(serializers.Serializer):
    # FileField, not ImageField: image_utils.validate_upload() is the single
    # authority on upload validity (content-type + size), called inside
    # create_user_photo. ImageField would additionally Pillow-decode here,
    # a stricter contract than the rest of the codebase applies.
    image = serializers.FileField()
    event = serializers.CharField(required=False, allow_blank=True, default="")
    caption = serializers.CharField(max_length=255, allow_blank=True, default="")


class _BlankToNone:
    """Field mixin: treat "" as null.

    Multipart forms can't send a real null — clearing an optional field arrives
    as an empty string, which DateTimeField/IntegerField/FloatField would reject.
    """
    def validate_empty_values(self, data):
        if data == "":
            data = None
        return super().validate_empty_values(data)


class BlankableDateTimeField(_BlankToNone, serializers.DateTimeField):
    pass


class BlankableIntegerField(_BlankToNone, serializers.IntegerField):
    pass


class BlankableFloatField(_BlankToNone, serializers.FloatField):
    pass


class EventWriteSerializer(serializers.ModelSerializer):
    """Input side of event create (POST, full) and update (PATCH, partial).

    Fields are declared explicitly where the API contract differs from the
    model: `name` is required here (the model has a default), `date` is
    optional here (the model requires it but the UI treats it as optional),
    and nullable fields accept "" as "clear". Everything else (rules,
    survey_url, visibility flags, image/logo) is derived from the model.
    """
    name = serializers.CharField(max_length=255)
    date = BlankableDateTimeField(required=False, allow_null=True)
    end_date = BlankableDateTimeField(required=False, allow_null=True)
    points = serializers.IntegerField(min_value=0, default=0)
    capacity = BlankableIntegerField(min_value=0, required=False, allow_null=True)
    latitude = BlankableFloatField(min_value=-90, max_value=90,
                                   required=False, allow_null=True)
    longitude = BlankableFloatField(min_value=-180, max_value=180,
                                    required=False, allow_null=True)
    checkin_radius = serializers.IntegerField(min_value=10, max_value=50000,
                                              required=False)
    # FileField (not the auto ImageField): accepts SVG logos. The poster `image`
    # stays the default ImageField — it's raster-only because Event.save()
    # downscales it. validate_logo_file keeps it to image/SVG types + a size cap.
    logo = serializers.FileField(required=False, allow_null=True,
                                 validators=[validate_logo_file])

    class Meta:
        model = Event
        fields = [
            "name", "description", "place", "date", "end_date", "points",
            "capacity", "rules", "survey_url", "visible_to_users",
            "visible_to_close", "latitude", "longitude", "checkin_radius",
            "category", "image", "logo",
        ]

    def validate(self, attrs):
        # Same pairing rule as Event.clean() — DRF never calls model.clean(),
        # so it lives here too. On PATCH, fall back to the instance's values
        # so sending just one coordinate can't break the pair.
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lon = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (lat is None) != (lon is None):
            raise serializers.ValidationError(
                "Zadej zeměpisnou šířku i délku, nebo ani jednu.")
        return attrs


# --- Read-response serializers (document what GET endpoints return) ---
# These mirror the dicts built in leaderboard.services; they exist for the API
# schema, not for runtime serialization (the views return the service dicts).

class SeasonSerializer(serializers.Serializer):
    """A season (leaderboard.services.catalog.season_dict)."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField()
    is_active = serializers.BooleanField()


class SeasonsResponseSerializer(serializers.Serializer):
    seasons = SeasonSerializer(many=True)


class LeaderboardEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.IntegerField()
    total_points = serializers.IntegerField()
    events_count = serializers.IntegerField()
    profile_username = serializers.CharField(allow_null=True, help_text="Linked account, if any.")
    photo = serializers.URLField(allow_null=True)


class LeaderboardResponseSerializer(serializers.Serializer):
    season = SeasonSerializer(allow_null=True, help_text="null for the all-time board.")
    entries = LeaderboardEntrySerializer(many=True)


class StatsResponseSerializer(serializers.Serializer):
    players = serializers.IntegerField()
    events = serializers.IntegerField()
    points = serializers.IntegerField()


class HeroEventSerializer(serializers.Serializer):
    url = serializers.URLField()
    name = serializers.CharField()
    date = serializers.DateTimeField(allow_null=True)
    slug = serializers.CharField()


class HeroResponseSerializer(serializers.Serializer):
    hero_events = HeroEventSerializer(many=True)


class CheckinEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    date = serializers.DateTimeField(allow_null=True)
    points = serializers.IntegerField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    checkin_radius = serializers.IntegerField()
    checkin_window_end = serializers.DateTimeField(allow_null=True)


class CheckinEventsResponseSerializer(serializers.Serializer):
    events = CheckinEventSerializer(many=True)


class CategoriesResponseSerializer(serializers.Serializer):
    categories = CategorySerializer(many=True)


class _PlayerEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    place = serializers.CharField()
    date = serializers.DateTimeField(allow_null=True)
    points = serializers.IntegerField()
    category = CategorySerializer(allow_null=True)


class _PlayerSeasonSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    start = serializers.DateField()
    end = serializers.DateField()
    is_active = serializers.BooleanField()
    season_pts = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)


class PlayerDetailSerializer(serializers.Serializer):
    """Public leaderboard-player profile (leaderboard.services.player_payload)."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    total_points = serializers.IntegerField()
    events_count = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    profile_username = serializers.CharField(allow_null=True, help_text="Linked account, if any.")
    events = _PlayerEventSerializer(many=True)
    seasons = _PlayerSeasonSummarySerializer(many=True)


class GalleryPhotoSerializer(serializers.Serializer):
    url = serializers.URLField()
    url_mobile = serializers.URLField(allow_null=True)
    event_name = serializers.CharField(allow_blank=True)
    event_slug = serializers.CharField(allow_blank=True)
    event_date = serializers.DateTimeField(allow_null=True)
    is_user_photo = serializers.BooleanField()
    uploaded_by = serializers.CharField(allow_blank=True)


class GalleryResponseSerializer(serializers.Serializer):
    photos = GalleryPhotoSerializer(many=True)
    count = serializers.IntegerField()
    has_more = serializers.BooleanField()


class _AdminFeedbackUserSerializer(serializers.Serializer):
    name = serializers.CharField()
    attended_events = serializers.IntegerField()


class _AdminFeedbackEventSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    date = serializers.DateTimeField(allow_null=True)


class AdminFeedbackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    rating = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    user = _AdminFeedbackUserSerializer()
    event = _AdminFeedbackEventSerializer()


class AdminFeedbacksResponseSerializer(serializers.Serializer):
    feedbacks = AdminFeedbackSerializer(many=True)


# --- Admin: attendance + RSVP management for one event ---

class AttendeeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="Leaderboard user id (see /players/<id>/).")
    name = serializers.CharField()
    points = serializers.IntegerField()
    profile_username = serializers.CharField(allow_null=True, help_text="Linked account, if any.")


class AttendeesResponseSerializer(serializers.Serializer):
    attendees = AttendeeSerializer(many=True)


class AttendeeWriteSerializer(serializers.Serializer):
    points = serializers.IntegerField(min_value=0)


class RsvpEntrySerializer(serializers.Serializer):
    auth_user_id = serializers.IntegerField()
    name = serializers.CharField()
    username = serializers.CharField()
    created_at = serializers.DateTimeField()


class RsvpsResponseSerializer(serializers.Serializer):
    rsvps = RsvpEntrySerializer(many=True)
