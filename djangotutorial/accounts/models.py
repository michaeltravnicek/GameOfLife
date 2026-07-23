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
    # Privacy flags — NOT ENFORCED YET. All three are stored and round-tripped
    # through the profile API, but nothing reads them to actually hide anything
    # (profile_payload always returns full data; no display code checks them).
    #   hide_pts      — no UI toggle either; fully dormant.
    #   hide_events   — has an edit-page toggle, but display doesn't honor it.
    #   members_only  — has an edit-page toggle, but display doesn't honor it.
    # See FRONTEND_TODO.md (privacy flags) before relying on these.
    _NOT_ENFORCED = "ZATÍM NEVYNUCENO: hodnota se uloží, ale nic podle ní neskrývá."
    hide_pts = models.BooleanField(
        default=False,
        help_text=f"Skrýt body na profilu. {_NOT_ENFORCED} Navíc nemá přepínač v UI.",
    )
    hide_events = models.BooleanField(
        default=False, help_text=f"Skrýt seznam akcí na profilu. {_NOT_ENFORCED}",
    )
    members_only = models.BooleanField(
        default=False, help_text=f"Profil jen pro přihlášené. {_NOT_ENFORCED}",
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
