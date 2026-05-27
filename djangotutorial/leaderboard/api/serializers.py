from rest_framework import serializers

from leaderboard.models import Category, Event, EventFeedback, EventRSVP, ImageToEvent, UserPhoto


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class EventListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "slug", "name", "description", "place",
            "date", "points", "image", "capacity", "is_past", "category",
            "visible_to_users",
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


class EventDetailSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    rsvp_count = serializers.SerializerMethodField()
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
            "points", "image", "logo", "rules", "capacity",
            "latitude", "longitude", "category",
            "survey_url", "visible_to_users",
            "is_past", "rsvp_count", "is_full", "has_rsvp",
            "has_attended", "feedback_given",
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

    def _rsvp_count(self, obj):
        # Memoize per instance — rsvp_count + is_full both need it.
        if not hasattr(obj, "_cached_rsvp_count"):
            obj._cached_rsvp_count = obj.rsvps.count()
        return obj._cached_rsvp_count

    def get_rsvp_count(self, obj):
        return self._rsvp_count(obj)

    def get_is_full(self, obj):
        if obj.capacity is None:
            return False
        return self._rsvp_count(obj) >= obj.capacity

    def get_has_rsvp(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return EventRSVP.objects.filter(auth_user=request.user, event=obj).exists()

    def get_has_attended(self, obj):
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

    def get_feedback_given(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return EventFeedback.objects.filter(auth_user=request.user, event=obj).exists()

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
