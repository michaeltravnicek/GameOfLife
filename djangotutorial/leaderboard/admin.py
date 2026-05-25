from django.contrib import admin
from .models import Category, Event, EventFeedback, EventRSVP, ImageToEvent, LastUpdate, ProfileAnswer, ProfileQuestion, Season, User, UserPhoto, UserToEvent


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "date", "place", "points", "visible_to_users")
    list_filter = ("category", "visible_to_users")
    search_fields = ("name", "description")
    fieldsets = (
        (None, {
            "fields": ("name", "category", "description", "rules", "date", "end_date",
                       "points", "capacity", "image", "logo", "visible_to_users", "survey_url")
        }),
        ("Místo a check-in", {
            "description": "Vyplňte souřadnice pro aktivaci mapy a check-in tlačítka. Souřadnice najdete na maps.google.com (pravý klik → 'Co je tady?').",
            "fields": ("place", "latitude", "longitude", "checkin_radius"),
        }),
        ("Technické (Google Sheets — volitelné)", {
            "classes": ("collapse",),
            "fields": ("sheet_id", "sheet_list_id", "slug"),
        }),
    )


@admin.register(ImageToEvent)
class ImageToEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "image")
    search_fields = ("event_id",)


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
    list_display = ("auth_user", "event", "rating", "updated_at")
    list_filter = ("event", "rating")
    search_fields = ("auth_user__username",)


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