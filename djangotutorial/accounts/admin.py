from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "leaderboard_user", "created_at")
    search_fields = ("user__username", "user__email", "leaderboard_user__name", "leaderboard_user__number")
    raw_id_fields = ("user", "leaderboard_user")
