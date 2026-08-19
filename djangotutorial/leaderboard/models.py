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
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="season_end_after_start",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .cache_config import invalidate_season_caches
        invalidate_season_caches()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from .cache_config import invalidate_season_caches
        invalidate_season_caches()


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # The category list is cached for an hour, and both the event form and
        # the events filter read it — a category added here must be pickable now,
        # not next hour. Best-effort: a cache outage must not break the write.
        from .cache_config import invalidate_category_cache
        invalidate_category_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .cache_config import invalidate_category_cache
        invalidate_category_cache()
        return result

    def __str__(self):
        return self.name


class Badge(models.Model):
    """A collectible emblem, shared by the events that award it.

    This is also the one and only home of event artwork. Events used to carry
    their own `logo` ImageField, which meant re-uploading the same file for every
    edition -- 135 logo files on disk turned out to be 7 distinct images, one of
    them stored 72 times. The artwork lives here once and events point at it.

    Attending an event that has a badge earns the attendee a copy in their
    collection -- see UserBadge and leaderboard.signals. So attaching a badge to
    an event is two decisions at once: which logo it shows, and which emblem its
    attendees collect.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    # The emblem artwork, doubling as the logo every event using this badge
    # renders. Downscaled to 512px on save (format preserved, so transparent
    # PNG / SVG / GIF survive).
    image = models.ImageField(upload_to="badges/", blank=True, null=True)
    # Artwork comes in wildly different intrinsic sizes and padding, so the same
    # CSS box renders some huge and some tiny. This multiplier normalizes the
    # displayed size (1.0 = unchanged, applied as a CSS scale). It lives on the
    # artwork rather than on the event: 72 events sharing one logo would
    # otherwise need the same correction set 72 times.
    image_scale = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(5.0)],
        help_text="Zvětšení/zmenšení obrázku při zobrazení. 1.0 = beze změny.",
    )
    description = models.TextField(
        blank=True, default="",
        help_text="Volitelný popis odznaku (za co se uděluje).",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "odznak"
            slug = base
            n = 2
            while Badge.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)
        if self.image:
            # Rendered inside a small box (scaled by image_scale), so 512 is
            # plenty. No .mobile.webp sibling — at this size it would save
            # nothing and only add a file. SVG artwork is passed over untouched.
            from .image_utils import process_image_field
            process_image_field(self, "image")

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
    # The event's logo AND the emblem its attendees collect — one artwork, one
    # row, however many editions reuse it. Replaced the old per-event `logo`
    # ImageField, which stored the same file once per event.
    # SET_NULL: deleting a badge must not cascade-delete events; they just lose
    # their logo.
    badge = models.ForeignKey(
        "Badge", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="events",
        help_text="Logo akce — zároveň odznak, který účastníci získají do sbírky.",
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
                condition=(models.Q(latitude__isnull=True, longitude__isnull=True)
                       | models.Q(latitude__isnull=False, longitude__isnull=False)),
                name="event_latlng_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(checkin_radius__gte=1),
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
            from .image_utils import process_image_field
            process_image_field(self, "image")
        # Best-effort: a cache outage must not break saving an event.
        from .cache_config import invalidate_event_caches
        invalidate_event_caches()

    def __str__(self):
        return f"{self.name} - {self.date} - {self.place} - {self.sheet_id}"

    def delete(self, *args, **kwargs):
        """Same eviction as save(). Without it a deleted event lingered in the
        hero carousel (1 h TTL) and the city filter (30 min) — the one moment a
        stale cache is most obvious, because someone just removed the thing."""
        super().delete(*args, **kwargs)
        from .cache_config import invalidate_event_caches
        invalidate_event_caches()

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
            from .image_utils import process_image_field
            process_image_field(self, "image")
        from .cache_config import invalidate_hero_cache
        invalidate_hero_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from .cache_config import invalidate_hero_cache
        invalidate_hero_cache()


class ActivePlayerManager(models.Manager):
    """Players that still stand on their own — merged-away rows excluded.

    This is `User.objects`, so every query written in app code is merge-safe by
    default. Code that genuinely needs the merged rows (the admin, the merge
    tool itself, `dumpdata`) asks for `User.all_objects`.
    """

    def get_queryset(self):
        return super().get_queryset().filter(merged_into__isnull=True)


class User(models.Model):
    """A player on the leaderboard. Exists with or without a site account.

    Identity used to be the phone number: the Google Form asked for one and
    ``number`` was the key the sheet sync matched on. That field is gone
    (migration 0026) — a phone number collected only to act as a join key is
    data with no purpose, which is exactly what data minimisation forbids.

    Since registration creates a player (accounts.services.ensure_leaderboard_user),
    an account *is* a player and the identity is exact for everyone who signed up.
    What is left over is the pre-registration archive: rows imported from the
    Google Forms era whose human later made an account. Attaching those is a
    merge of two players, not a link -- see ``leaderboard/merging.py``.
    """

    name = models.CharField(max_length=255)
    # Null, not blank: players imported from older sheets have no e-mail at all,
    # and `unique` must not collapse them into one row. Postgres allows many
    # NULLs in a unique column but only one "". Always store None, never "".
    email = models.EmailField(
        null=True, blank=True, unique=True,
        help_text="E-mail z formuláře — spojuje odpovědi téhož člověka. Prázdné u starších hráčů.",
    )
    # Soft merge: the row survives its own merge so a mistake is one UPDATE away
    # from being undone. A hard delete would need a database restore instead.
    # PROTECT, not SET_NULL: clearing this on the target's deletion would silently
    # resurrect the archive row into the leaderboard, points and all.
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="merged_from",
        help_text="Vyplněné = tento hráč byl sloučen do jiného a nezobrazuje se.",
    )
    merged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    objects = ActivePlayerManager()
    all_objects = models.Manager()

    class Meta:
        # Both point at the unfiltered manager on purpose. `base_manager_name`
        # keeps `profile.leaderboard_user` resolvable after a merge (a filtered
        # base manager raises DoesNotExist instead). `default_manager_name` is
        # what the admin and `dumpdata` use -- a backup that quietly omitted
        # merged players would lose exactly the rows a merge might need undoing.
        base_manager_name = "all_objects"
        default_manager_name = "all_objects"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # The cached leaderboard stores the *rendered* name (shortened to
        # "Jan N." unless consented), so a rename that skipped this would leave
        # the old name on the board until the TTL expired. Only on a real change:
        # the Sheets sync saves players constantly without touching the name.
        renamed = False
        if self.pk:
            previous = type(self).all_objects.filter(pk=self.pk).values_list(
                "name", flat=True).first()
            renamed = previous is not None and previous != self.name

        super().save(*args, **kwargs)

        if renamed:
            from .cache_config import invalidate_points_dependent_caches
            invalidate_points_dependent_caches()


class UserToEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    points = models.IntegerField()

    class Meta:
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user} → {self.event}"

    # Attendance is the leaderboard's only input, so every write has to evict it.
    # The four *callers* that create attendance (check-in, the sync, the award
    # command, the admin attendance editor) used to each remember this on their
    # own -- and the admin, which is the documented way to top up somebody whose
    # phone failed, did not. Doing it here means a row cannot be written from
    # anywhere without the board following.
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .cache_config import invalidate_points_dependent_caches
        invalidate_points_dependent_caches()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .cache_config import invalidate_points_dependent_caches
        invalidate_points_dependent_caches()
        return result


class UserBadge(models.Model):
    """One earned badge in a leaderboard player's collection.

    Keyed on the leaderboard User (not the account) because that is what
    attendance keys on -- so a Google-Sheets player collects badges too, and
    they follow the player when an account links to them.

    unique_together (user, badge): a badge is collected once, however many of its
    events you attend. `event` records which attendance first earned it (kept
    even if that attendance is later removed -- the badge stays collected).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    # SET_NULL so removing the source attendance's event doesn't revoke the badge.
    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="awarded_badges",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")
        ordering = ["-awarded_at"]

    def __str__(self):
        return f"{self.user} ← {self.badge}"


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
                condition=models.Q(rating__gte=1, rating__lte=10),
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
            from .image_utils import process_image_field
            process_image_field(self, "image")

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Questions are authored in Django admin and the list is cached for an
        # hour. Without this, an edit sits invisible until the TTL expires and
        # reads as "the admin didn't save it".
        from .cache_config import invalidate_profile_questions_cache
        invalidate_profile_questions_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .cache_config import invalidate_profile_questions_cache
        invalidate_profile_questions_cache()
        return result

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
