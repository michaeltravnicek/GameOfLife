from django.contrib import admin, messages

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "leaderboard_user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "leaderboard_user__name", "leaderboard_user__number")
    raw_id_fields = ("user", "leaderboard_user")

    def save_model(self, request, obj, form, change):
        # Assigning the admin role here also grants Django admin access. This is
        # the one explicit place that escalates privileges — Profile.save() no
        # longer does it implicitly (see grant_django_admin_access docstring).
        super().save_model(request, obj, form, change)
        if obj.role == Profile.ROLE_ADMIN and obj.grant_django_admin_access():
            self.message_user(
                request,
                f"Účtu {obj.user.username} byl udělen přístup do Django adminu "
                f"(is_staff + is_superuser).",
                messages.WARNING,
            )
