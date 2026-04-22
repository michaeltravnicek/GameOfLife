from django.conf import settings
from django.db import models

from leaderboard.models import User as LeaderboardUser


class Profile(models.Model):
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
    instagram = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"

    @property
    def phone(self):
        if self.leaderboard_user_id is None:
            return None
        return self.leaderboard_user.number

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.photo:
            from leaderboard.image_utils import resize_image
            resize_image(self.photo, max_width=400, max_height=400, quality=85)
