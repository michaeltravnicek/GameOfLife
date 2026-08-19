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
    # Privacy flags — enforced server-side by leaderboard.privacy.visibility_for,
    # which every profile/player payload and season sub-resource routes through.
    # The owner and admins are never gated; see that function for why.
    hide_pts = models.BooleanField(
        default=False,
        help_text="Skrýt body a pořadí na profilu.",
    )
    hide_events = models.BooleanField(
        default=False, help_text="Skrýt seznam akcí na profilu.",
    )
    members_only = models.BooleanField(
        default=False, help_text="Profil jen pro přihlášené (pro nepřihlášené vrací 404).",
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, blank=True, default=ROLE_NONE,
        help_text="Administrátor má přístup do Django adminu a vidí feedbacky. Fotograf může nahrávat oficiální fotky k akcím.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # GDPR accountability (Art. 5(2) / 7(1)): it is not enough that the user
    # ticked a box — the controller has to be able to *demonstrate* it later.
    # Storing the moment and the document version means a consent given against
    # an older text can be told apart from one given against the current one,
    # which is what makes a re-consent campaign possible after a material change.
    #
    # Null for accounts created before this field existed; those users have not
    # agreed to anything and must not be presented as if they had.
    gdpr_consent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Kdy uživatel potvrdil seznámení se zásadami ochrany osobních údajů.",
    )
    gdpr_consent_version = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Verze zásad, se kterou uživatel souhlasil (např. 2026-07-22).",
    )

    def __str__(self):
        return f"Profile<{self.user.username}>"

    @property
    def has_current_gdpr_consent(self):
        """True when consent exists *and* matches the policy in force."""
        from django.conf import settings as django_settings

        return bool(
            self.gdpr_consent_at
            and self.gdpr_consent_version == django_settings.PRIVACY_POLICY_VERSION
        )

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
        # Read the stored values before writing. Both of these end up inside the
        # *cached* leaderboard payload — hide_pts decides whether this player is
        # on the board at all, and the avatar is rendered into their row. Without
        # this the change appears to do nothing until the TTL expires, which
        # reads as "the setting is broken".
        previous = None
        if self.pk:
            previous = (
                Profile.objects.filter(pk=self.pk)
                .values_list("hide_pts", "photo").first()
            )
        previous_hide_pts, previous_photo = previous if previous else (None, None)

        super().save(*args, **kwargs)

        # `or ""` on both sides: an unset ImageField reads back as "" from the
        # database but as None on the instance, so a bare != would call every
        # single profile save a photo change and evict the board each time.
        photo_changed = (previous_photo or "") != (self.photo.name or "")
        if previous_hide_pts != self.hide_pts or photo_changed:
            from leaderboard.cache_config import invalidate_points_dependent_caches
            invalidate_points_dependent_caches()

        if self.photo:
            from leaderboard.image_utils import process_image_field
            process_image_field(self, "photo")

    def grant_django_admin_access(self):
        """Give the linked account is_staff + is_superuser so /admin/ works.

        Deliberately NOT called from save(): granting superuser as a side effect
        of persisting a profile means any code path that happens to save a
        profile with role=admin silently escalates privileges. Callers ask for
        it explicitly — see accounts.admin.ProfileAdmin.save_model.
        Revoking stays manual (never strip flags off an existing superuser).
        """
        user = self.user
        if not (user.is_staff and user.is_superuser):
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
            return True
        return False
