from django.conf import settings
from django.db import models

from leaderboard.models import User as LeaderboardUser


class Profile(models.Model):
    ROLE_NONE = ""
    ROLE_CLOSE = "close"
    ROLE_PHOTOGRAPHER = "photographer"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_NONE, "Bez role"),
        (ROLE_CLOSE, "Close (může vytvářet akce)"),
        (ROLE_PHOTOGRAPHER, "Fotograf"),
        (ROLE_ADMIN, "Administrátor"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    leaderboard_user = models.OneToOneField(
        LeaderboardUser,
        on_delete=models.SET_NULL,
        related_name="profile",
        null=True,
        blank=True,
    )
    photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    bio = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    instagram = models.CharField(max_length=255, blank=True, default="")
    strava = models.CharField(max_length=255, blank=True, default="")
    spotify = models.CharField(max_length=255, blank=True, default="")
    tiktok = models.CharField(max_length=255, blank=True, default="")
    favourite_categories = models.ManyToManyField(
        'leaderboard.Category', blank=True, related_name='fans',
    )
    hide_pts = models.BooleanField(default=False)
    hide_events = models.BooleanField(default=False)
    members_only = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, blank=True, default=ROLE_NONE,
        help_text="Administrátor má přístup do Django adminu a vidí feedbacky. Fotograf může nahrávat oficiální fotky k akcím.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"

    @property
    def phone(self):
        if self.leaderboard_user_id is None:
            return None
        return self.leaderboard_user.number

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_photographer(self):
        return self.role == self.ROLE_PHOTOGRAPHER

    @property
    def is_close(self):
        return self.role == self.ROLE_CLOSE

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.photo:
            from leaderboard.image_utils import resize_image, make_webp_variant
            resize_image(self.photo, max_width=400, max_height=400, quality=85)
            make_webp_variant(self.photo, max_width=200, quality=60)
        # Grant Django auth flags when admin role is assigned, so /admin/ access works.
        # Removal is intentionally manual (don't strip flags from existing superusers).
        if self.role == self.ROLE_ADMIN:
            user = self.user
            if not (user.is_staff and user.is_superuser):
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
