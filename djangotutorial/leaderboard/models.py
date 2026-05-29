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
    description = models.CharField(max_length=1023, default="")
    place = models.CharField(max_length=255)
    date = models.DateTimeField()
    points = models.IntegerField()
    image = models.ImageField(upload_to="event_images/", blank=True, null=True)
    logo = models.ImageField(upload_to="event_logos/", blank=True, null=True)
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
        blank=True, default="",
        help_text="Volitelný dotazník. Zobrazí se uživateli po přihlášení na akci.",
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
            from .image_utils import resize_image
            resize_image(self.image, max_width=1200, max_height=1200, quality=85)
        # Best-effort: a cache outage must not break saving an event.
        from .cache_config import invalidate_event_caches
        invalidate_event_caches()

    def __str__(self):
        return f"{self.name} - {self.date} - {self.place} - {self.sheet_id}"

    @property
    def checkin_window_end(self):
        from datetime import timedelta
        return self.end_date if self.end_date else self.date + timedelta(hours=4)


class ImageToEvent(models.Model):
    event_id = models.ForeignKey(Event, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="event_images/", blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            from .image_utils import resize_image
            resize_image(self.image, max_width=1024, max_height=1024, quality=75)
        from .cache_config import invalidate_hero_cache
        invalidate_hero_cache()


class User(models.Model):
    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)

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
    auth_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="feedbacks")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("auth_user", "event")

    def __str__(self):
        return f"Feedback {self.rating}★ {self.auth_user} → {self.event}"


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
            from .image_utils import resize_image
            resize_image(self.image, max_width=1600, max_height=1600, quality=80)

    def __str__(self):
        return f"{self.auth_user} → {self.event or 'bez akce'}"


class PhotoLike(models.Model):
    photo = models.ForeignKey(UserPhoto, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="photo_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("photo", "user")

    def __str__(self):
        return f"{self.user} ♥ photo#{self.photo_id}"


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
