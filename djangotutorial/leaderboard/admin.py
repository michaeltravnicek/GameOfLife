from django.contrib import admin
from .models import Event, UserToEvent, ImageToEvent, User, ProfileQuestion, ProfileAnswer


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "date", "place", "points")
    search_fields = ("name", "description")


@admin.register(ImageToEvent)
class ImageToEvent(admin.ModelAdmin):
    list_display = ("event_id", "image")
    search_fields = ("event_id",)

@admin.register(User)
class UserToAdmin(admin.ModelAdmin):
    list_display = ("number", "name")

@admin.register(UserToEvent)
class UserToEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event")
    list_filter = ("event",)


@admin.register(ProfileQuestion)
class ProfileQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "order")
    ordering = ("order",)


@admin.register(ProfileAnswer)
class ProfileAnswerAdmin(admin.ModelAdmin):
    list_display = ("auth_user", "question", "updated_at")
    list_filter = ("question", "updated_at")
    search_fields = ("auth_user__username", "auth_user__first_name")