from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class Season(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            # Partial unique index: any number of inactive seasons, at most
            # one active — the leaderboard's "current season" must be unambiguous.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="season_single_active",
            ),
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F("start_date")),
                name="season_end_after_start",
            ),
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    # Google Sheets is optional — events can be created manually in the admin.
    sheet_id = models.CharField(max_length=255, blank=True, default="")
    sheet_list_id = models.CharField(max_length=255, blank=True, default="")
    name = models.CharField(max_length=255, default="Akce")
    description = models.TextField(blank=True, default="")
    place = models.CharField(max_length=255)
    # Nullable: legacy sheet events and drafts may have no date yet. The API
    # and admin have always treated it as optional — the NOT NULL column was
    # a leftover that 500'd event creation without a date.
    date = models.DateTimeField(null=True, blank=True)
    # "Čas upřesníme": the start date is set but the exact start time isn't
    # finalized yet. `date` still stores a datetime (so is_past / check-in /
    # ordering keep working off the day), the UI just shows "Upřesníme" in
    # place of the clock time.
    time_tbd = models.BooleanField(
        default=False,
        help_text="Čas upřesníme: datum je dané, ale přesný začátek ještě ne. "
                  "Místo času se zobrazí „Upřesníme“.",
    )
    points = models.IntegerField()
    image = models.ImageField(upload_to="event_images/", blank=True, null=True)
    logo = models.ImageField(upload_to="event_logos/", blank=True, null=True)
    # Logos come in wildly different intrinsic sizes/padding, so the same CSS box
    # renders some huge and some tiny. This per-event multiplier lets an admin
    # normalize the displayed size (1.0 = unchanged, applied as a CSS scale).
    logo_scale = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(5.0)],
        help_text="Zvětšení/zmenšení loga při zobrazení. 1.0 = beze změny.",
    )
    rules = models.TextField(blank=True, default="")
    capacity = models.IntegerField(null=True, blank=True)
    visible_to_users = models.BooleanField(
        default=True,
        help_text="Pokud vypnuto, akce se nezobrazuje uživatelům (jen v adminu).",
    )
    visible_to_close = models.BooleanField(
        default=False,
        help_text="Náhled pro Close: pokud zapnuto, akci uvidí role Close (a vyšší) i když je 'Viditelná pro uživatele' vypnutá.",
    )
    survey_url = models.URLField(
        max_length=500, blank=True, default="",
        help_text="Volitelný dotazník. Zobrazí se uživateli po přihlášení na akci.",
    )
    whatsapp_url = models.URLField(
        max_length=500, blank=True, default="",
        help_text="Odkaz na WhatsApp skupinu akce. Nabídne se uživateli po "
                  "přihlášení (spolu s dotazníkem).",
    )
    end_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Konec check-in okna. Pokud nevyplněno, použije se začátek + 4 hodiny."
    )
    latitude = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Zeměpisná šířka (např. 49.1951). Povinné pro mapu a check-in."
    )
    longitude = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Zeměpisná délka (např. 16.6068). Povinné pro mapu a check-in."
    )
    checkin_radius = models.IntegerField(
        default=500,
        validators=[MinValueValidator(1)],
        help_text="Poloměr check-in zóny v metrech. Výchozí: 500 m."
    )

    category = models.ForeignKey(
        'Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events',
    )
    slug = models.SlugField(max_length=280, unique=True, null=True, blank=True)
    # null=True: creation time is unknown for rows that predate these columns.
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            # DB-level twin of clean(): bulk paths (sheets sync, updates)
            # bypass Python validation, so the pairing rule lives here too.
            models.CheckConstraint(
                check=(models.Q(latitude__isnull=True, longitude__isnull=True)
                       | models.Q(latitude__isnull=False, longitude__isnull=False)),
                name="event_latlng_pair",
            ),
            models.CheckConstraint(
                check=models.Q(checkin_radius__gte=1),
                name="event_checkin_radius_positive",
            ),
        ]

    def clean(self):
        # Geo check-in needs a full coordinate pair — reject a half-set location.
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError(
                "Zadej zeměpisnou šířku i délku, nebo ani jednu."
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "akce"
            slug = base
            n = 2
            while Event.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)
        if self.image:
            from .image_utils import resize_image, make_webp_variant
            resize_image(self.image, max_width=1200, max_height=1200, quality=85)
            make_webp_variant(self.image)
        # Best-effort: a cache outage must not break saving an event.
        from .cache_config import invalidate_event_caches
        invalidate_event_caches()

    def __str__(self):
        return f"{self.name} - {self.date} - {self.place} - {self.sheet_id}"

    @property
    def checkin_window_end(self):
        """End of the check-in window; None when the event has no dates at all."""
        from datetime import timedelta
        if self.end_date:
            return self.end_date
        return self.date + timedelta(hours=4) if self.date else None


class ImageToEvent(models.Model):
    # Named `event` (not `event_id`): the old name produced a DB column
    # `event_id_id` and read backwards in queries.
    event = models.ForeignKey(Event, on_delete=models.CASCADE,
                              related_name="official_images")
    image = models.ImageField(upload_to="event_images/", blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            from .image_utils import resize_image, make_webp_variant
            resize_image(self.image, max_width=1024, max_height=1024, quality=75)
            make_webp_variant(self.image)
        from .cache_config import invalidate_hero_cache
        invalidate_hero_cache()


class User(models.Model):
    # Czech mobile numbers are exactly 9 digits with no leading zero, so the
    # valid integer range is 100000000-999999999. Enforced both in Python
    # (forms/admin) and in the DB, since the Sheets sync writes in bulk.
    number = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(100_000_000), MaxValueValidator(999_999_999)],
        help_text="Telefon bez předvolby — přesně 9 číslic.",
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(number__gte=100_000_000, number__lte=999_999_999),
                name="user_number_9_digits",
            ),
        ]

    def __str__(self):
        return self.name


class UserToEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    points = models.IntegerField()

    class Meta:
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user} → {self.event}"


class LastUpdate(models.Model):
    last_update = models.DateTimeField(auto_now=True)
    last_complete_update = models.DateTimeField(blank=True, null=True)


class EventRSVP(models.Model):
    auth_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rsvps",
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("auth_user", "event")

    def __str__(self):
        return f"RSVP {self.auth_user} → {self.event}"


class EventFeedback(models.Model):
    """A 1–10 rating + optional comment for an event.

    Keyed on the leaderboard ``User``, not the auth user: most feedback arrives
    from the Google Form sync, where a row identifies the person by phone number
    only and no account exists. The web form resolves the auth user to their
    linked leaderboard user before writing — it is already gated on attendance,
    which requires that link anyway.
    """

    SOURCE_WEB = "web"
    SOURCE_FORM = "form"
    SOURCE_CHOICES = [
        (SOURCE_WEB, "Web"),
        (SOURCE_FORM, "Google Form"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="feedbacks")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    comment = models.TextField(blank=True, default="")
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default=SOURCE_WEB)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "event")
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1, rating__lte=10),
                name="feedback_rating_1_10",
            ),
        ]

    def __str__(self):
        return f"Feedback {self.rating}/10 {self.user} → {self.event}"


class UserPhoto(models.Model):
    auth_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gallery_photos",
    )
    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_photos"
    )
    image = models.ImageField(upload_to="user_photos/")
    caption = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            from .image_utils import resize_image, make_webp_variant
            resize_image(self.image, max_width=1600, max_height=1600, quality=80)
            make_webp_variant(self.image)

    def __str__(self):
        return f"{self.auth_user} → {self.event or 'bez akce'}"


class PhotoLike(models.Model):
    photo = models.ForeignKey(UserPhoto, on_delete=models.CASCADE, related_name="likes")
    auth_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="photo_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("photo", "auth_user")

    def __str__(self):
        return f"{self.auth_user} ♥ photo#{self.photo_id}"


class ProfileQuestion(models.Model):
    text = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


class ProfileAnswer(models.Model):
    auth_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_answers",
    )
    question = models.ForeignKey(ProfileQuestion, on_delete=models.CASCADE)
    answer = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("auth_user", "question")

    def __str__(self):
        return f"{self.auth_user} → {self.question}"
