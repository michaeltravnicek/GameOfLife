from rest_framework import serializers

from .models import (
    Event,
    EventFeedback,
    EventRSVP,
    ImageToEvent,
    User,
    UserPhoto,
    UserToEvent,
)


class EventListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "slug", "name", "description", "place",
            "date", "points", "image", "capacity", "is_past",
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_is_past(self, obj):
        from django.utils import timezone
        return bool(obj.date and obj.date < timezone.now())


class EventImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ImageToEvent
        fields = ["id", "image"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class UserPhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = UserPhoto
        fields = ["id", "image", "caption", "uploaded_by", "created_at"]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_uploaded_by(self, obj):
        return obj.auth_user.get_full_name() or obj.auth_user.username


class EventDetailSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    rsvp_count = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    has_rsvp = serializers.SerializerMethodField()
    official_images = serializers.SerializerMethodField()
    user_photos = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "slug", "name", "description", "place", "date", "end_date",
            "points", "image", "logo", "rules", "capacity",
            "latitude", "longitude",
            "is_past", "rsvp_count", "is_full", "has_rsvp",
            "official_images", "user_photos",
        ]

    def _abs(self, image_field):
        if not image_field:
            return None
        request = self.context.get("request")
        url = image_field.url
        return request.build_absolute_uri(url) if request else url

    def get_image(self, obj):
        return self._abs(obj.image)

    def get_logo(self, obj):
        return self._abs(obj.logo)

    def get_is_past(self, obj):
        from django.utils import timezone
        return bool(obj.date and obj.date < timezone.now())

    def get_rsvp_count(self, obj):
        return obj.rsvps.count()

    def get_is_full(self, obj):
        if obj.capacity is None:
            return False
        return obj.rsvps.count() >= obj.capacity

    def get_has_rsvp(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return EventRSVP.objects.filter(auth_user=request.user, event=obj).exists()

    def get_official_images(self, obj):
        request = self.context.get("request")
        return [
            request.build_absolute_uri(img.image.url) if request else img.image.url
            for img in ImageToEvent.objects.filter(event_id=obj)
            if img.image
        ]

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


class LeaderboardEntrySerializer(serializers.Serializer):
    """Mirrors the annotated user objects produced by leaderboard_total/_month."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.IntegerField()
    total_points = serializers.IntegerField()
    events_count = serializers.IntegerField()
    profile_username = serializers.CharField(allow_null=True, required=False)


class GalleryPhotoSerializer(serializers.Serializer):
    url = serializers.CharField()
    event_name = serializers.CharField(allow_blank=True)
    event_slug = serializers.CharField(allow_blank=True)
    event_date = serializers.DateTimeField(allow_null=True)
    is_user_photo = serializers.BooleanField()
    uploaded_by = serializers.CharField(allow_blank=True)


class EventFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventFeedback
        fields = ["id", "rating", "comment", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
