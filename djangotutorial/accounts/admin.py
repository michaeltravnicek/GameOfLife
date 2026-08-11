from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from leaderboard import merging
from leaderboard.models import User as LeaderboardUser

from . import matching
from .models import Profile


def _player_stats(queryset):
    """Annotate players with what an admin needs to recognise them."""
    return queryset.annotate(
        total_points=Sum("usertoevent__points"),
        events_count=Count("usertoevent", distinct=True),
        last_event_at=Max("usertoevent__event__date"),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "leaderboard_user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "leaderboard_user__name")
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

    # ── Archive player → account merging ──────────────────────────────────
    # The queue runs from the archive side: every account owns a player from
    # registration, so what is left over is Google-Forms rows waiting for their
    # human. Confirming one folds it into the account's player
    # (leaderboard.merging). Suggestions come from accounts.matching; the write
    # is always an explicit admin action, because a wrong merge moves another
    # person's points *and* their event history onto a stranger.

    def get_urls(self):
        own = [
            path("merge/", self.admin_site.admin_view(self.merge_list_view),
                 name="accounts_profile_link_list"),
            path("merge/<int:player_id>/", self.admin_site.admin_view(self.merge_detail_view),
                 name="accounts_profile_link_detail"),
            path("merge/<int:player_id>/undo/", self.admin_site.admin_view(self.unmerge_view),
                 name="accounts_profile_unmerge"),
            path("link/<int:user_id>/unlink/", self.admin_site.admin_view(self.unlink_view),
                 name="accounts_profile_unlink"),
        ]
        return own + super().get_urls()

    def _check_perm(self, request):
        if not request.user.has_perm("accounts.change_profile"):
            raise PermissionDenied

    def _context(self, request, **extra):
        return {**self.admin_site.each_context(request),
                "opts": self.model._meta, **extra}

    def merge_list_view(self, request):
        """Archive players waiting for an owner, each with its best suggestion."""
        self._check_perm(request)
        accounts = list(matching.mergeable_accounts()[:500])
        rows = []
        for player in _player_stats(matching.archive_players())[:200]:
            candidates = matching.suggest_accounts(player, accounts, limit=1)
            rows.append({"player": player,
                         "top": candidates[0] if candidates else None})
        return render(request, "admin/accounts/link_list.html", self._context(
            request, title="Přiřadit archivní hráče k účtům", rows=rows,
            account_count=len(accounts),
            merged=LeaderboardUser.all_objects.filter(
                merged_into__isnull=False).select_related("merged_into")[:50],
            orphan_accounts=matching.accounts_without_player().count(),
        ))

    def merge_detail_view(self, request, player_id):
        """Ranked accounts for one archive player; POST confirms the merge."""
        self._check_perm(request)
        player = get_object_or_404(_player_stats(matching.archive_players()), pk=player_id)

        if request.method == "POST":
            return self._do_merge(request, player)

        candidates = matching.suggest_accounts(
            player, list(matching.mergeable_accounts()[:500]), limit=8)
        return render(request, "admin/accounts/link_detail.html", self._context(
            request, title=f"Přiřadit hráče {player.name}",
            player=player, candidates=candidates,
        ))

    def _do_merge(self, request, player):
        account_id = request.POST.get("account_id")
        account = (
            matching.mergeable_accounts().filter(pk=account_id).first()
            if account_id else None
        )
        if account is None:
            raise Http404("Účet neexistuje nebo nemá hráče.")

        target = account.profile.leaderboard_user
        try:
            moved = merging.merge_players(
                player, target, performed_by=request.user.username)
        except merging.MergeError as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return redirect(reverse("admin:accounts_profile_link_detail",
                                    args=[player.pk]))

        self.message_user(
            request,
            f"Hráč {player.name} sloučen do účtu {account.username}: "
            f"{moved['attendance']} účastí, {moved['badges']} odznaků, "
            f"{moved['feedback']} hodnocení. Sloučení jde vrátit.",
            messages.SUCCESS,
        )
        return redirect(reverse("admin:accounts_profile_link_list"))

    def unmerge_view(self, request, player_id):
        """Undo a merge. POST only — it changes the leaderboard."""
        self._check_perm(request)
        if request.method != "POST":
            raise Http404
        player = get_object_or_404(
            LeaderboardUser.all_objects, pk=player_id, merged_into__isnull=False)
        try:
            merging.unmerge_players(player)
        except merging.MergeError as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return redirect(reverse("admin:accounts_profile_link_list"))
        self.message_user(
            request,
            f"Hráč {player.name} je zpátky v žebříčku. Body a odznaky, které "
            f"sloučení přesunulo, ale zůstaly u cílového účtu — zkontroluj je.",
            messages.WARNING,
        )
        return redirect(reverse("admin:accounts_profile_link_list"))

    def unlink_view(self, request, user_id):
        """Undo a link. POST only — this changes what a person can see."""
        self._check_perm(request)
        if request.method != "POST":
            raise Http404
        profile = get_object_or_404(Profile, user_id=user_id)
        player_name = profile.leaderboard_user.name if profile.leaderboard_user else "—"
        with transaction.atomic():
            profile.leaderboard_user = None
            profile.save(update_fields=["leaderboard_user"])
        from leaderboard.cache_config import invalidate_points_dependent_caches
        invalidate_points_dependent_caches()
        self.message_user(request,
                          f"Účet {profile.user.username} odpojen od hráče {player_name}.",
                          messages.WARNING)
        return redirect(reverse("admin:accounts_profile_changelist"))

    def changelist_view(self, request, extra_context=None):
        """Surface the merge tool from the Profile changelist."""
        pending = matching.archive_players().count()
        extra_context = {
            **(extra_context or {}),
            "link_tool_url": reverse("admin:accounts_profile_link_list"),
            "link_tool_pending": pending,
        }
        if pending:
            self.message_user(request, format_html(
                'Archivních hráčů bez účtu: {} — <a href="{}">přiřadit</a>',
                pending, reverse("admin:accounts_profile_link_list"),
            ), messages.INFO)
        return super().changelist_view(request, extra_context)
