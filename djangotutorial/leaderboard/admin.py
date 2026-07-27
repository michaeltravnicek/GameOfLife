from django.contrib import admin
from .models import Badge, Category, Event, EventFeedback, EventRSVP, ImageToEvent, LastUpdate, ProfileAnswer, ProfileQuestion, Season, User, UserBadge, UserToEvent, UserPhoto


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)

    def save_model(self, request, obj, form, change):
        # At most one active season (enforced by the season_single_active DB
        # constraint). Activating this one deactivates the rest first, so the
        # save can't collide with an already-active season. The admin wraps the
        # change form in a transaction, so the two writes are atomic.
        if obj.is_active:
            Season.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "date", "place", "points", "visible_to_users")
    list_filter = ("category", "visible_to_users")
    search_fields = ("name", "description")
    # NB: an explicit `fieldsets` is a whitelist — a model field left out here is
    # silently uneditable in the admin. Keep it in sync with Event's fields
    # (test_django_admin.AdminFieldCoverageTests enforces that).
    fieldsets = (
        (None, {
            "fields": ("name", "category", "badge", "description", "rules", "date", "time_tbd", "end_date",
                       "points", "capacity", "image",
                       "visible_to_users", "visible_to_close", "survey_url",
                       "whatsapp_url")
        }),
        ("Místo a check-in", {
            "description": "Souřadnice se obvykle nastavují přes mapu při vytváření akce na frontendu. Zde je lze ručně doladit.",
            "fields": ("place", "latitude", "longitude", "checkin_radius"),
        }),
        ("Technické (Google Sheets — volitelné)", {
            "classes": ("collapse",),
            "fields": ("sheet_id", "sheet_list_id", "slug"),
        }),
    )


@admin.register(ImageToEvent)
class ImageToEventAdmin(admin.ModelAdmin):
    list_display = ("event", "image")
    search_fields = ("event__name",)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("number", "name")


@admin.register(UserToEvent)
class UserToEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event")
    list_filter = ("event",)


@admin.register(EventRSVP)
class EventRSVPAdmin(admin.ModelAdmin):
    list_display = ("auth_user", "event", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("auth_user__username",)


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "rating", "source", "updated_at")
    list_filter = ("event", "rating", "source")
    search_fields = ("user__name", "user__number")


@admin.register(LastUpdate)
class LastUpdateAdmin(admin.ModelAdmin):
    list_display = ("last_update",)


@admin.register(UserPhoto)
class UserPhotoAdmin(admin.ModelAdmin):
    list_display = ("auth_user", "event", "caption", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("auth_user__username", "caption")


@admin.register(ProfileQuestion)
class ProfileQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "order")
    ordering = ("order",)


@admin.register(ProfileAnswer)
class ProfileAnswerAdmin(admin.ModelAdmin):
    list_display = ("auth_user", "question", "updated_at")
    list_filter = ("question", "updated_at")
    search_fields = ("auth_user__username", "auth_user__first_name")

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "events_count", "holders_count", "created_at")
    search_fields = ("name", "description")
    # slug is auto-derived in Badge.save(); showing it read-only avoids the
    # AdminFieldCoverageTests failure without inviting hand-edited slugs.
    readonly_fields = ("slug",)

    @admin.display(description="Akcí")
    def events_count(self, badge):
        return badge.events.count()

    @admin.display(description="Držitelů")
    def holders_count(self, badge):
        return badge.holders.count()


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    """Read-mostly: badges are awarded automatically by leaderboard.signals.

    Kept in the admin so a wrong award can be removed by hand, and so the
    field-coverage test has a home for every UserBadge field.
    """
    list_display = ("user", "badge", "event", "awarded_at")
    list_filter = ("badge",)
    search_fields = ("user__name", "badge__name")
    raw_id_fields = ("user", "badge", "event")
    readonly_fields = ("awarded_at",)
