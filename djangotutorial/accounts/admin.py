from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

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

    # ── Account ↔ player linking ──────────────────────────────────────────
    # Replaces the phone number as the way an account finds its points. The
    # suggestions come from accounts.matching; every write below is an explicit
    # admin action, never automatic — a wrong link hands someone another
    # person's points *and* their event history.

    def get_urls(self):
        own = [
            path("link/", self.admin_site.admin_view(self.link_list_view),
                 name="accounts_profile_link_list"),
            path("link/<int:user_id>/", self.admin_site.admin_view(self.link_detail_view),
                 name="accounts_profile_link_detail"),
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

    def link_list_view(self, request):
        """Accounts with no leaderboard player, each with its best suggestion."""
        self._check_perm(request)
        players = list(_player_stats(matching.unlinked_players()))
        rows = []
        for user in matching.unlinked_accounts()[:200]:
            candidates = matching.suggest_players(user, players, limit=1)
            rows.append({"account": user,
                         "top": candidates[0] if candidates else None})
        return render(request, "admin/accounts/link_list.html", self._context(
            request, title="Propojit účty s hráči", rows=rows,
            unlinked_players=len(players),
        ))

    def link_detail_view(self, request, user_id):
        """Ranked candidates for one account; POST confirms the chosen player."""
        self._check_perm(request)
        account = get_object_or_404(matching.unlinked_accounts(), pk=user_id)

        if request.method == "POST":
            return self._do_link(request, account)

        candidates = matching.suggest_players(
            account, list(_player_stats(matching.unlinked_players())), limit=8)
        return render(request, "admin/accounts/link_detail.html", self._context(
            request, title=f"Propojit účet {account.username}",
            account=account, candidates=candidates,
            signals=matching.account_signals(account),
        ))

    def _do_link(self, request, account):
        player_id = request.POST.get("player_id")
        try:
            player = LeaderboardUser.objects.get(pk=player_id)
        except (LeaderboardUser.DoesNotExist, ValueError, TypeError):
            raise Http404("Hráč neexistuje.")

        with transaction.atomic():
            # Re-check inside the transaction: two admins on this screen at once
            # would otherwise both pass the "unclaimed" test and the second write
            # would surface as a raw IntegrityError on the OneToOne.
            taken = (Profile.objects.select_for_update()
                     .filter(leaderboard_user=player).exclude(user=account).first())
            if taken is not None:
                self.message_user(
                    request,
                    f"Hráč {player.name} už patří účtu {taken.user.username}. "
                    f"Nejdřív ho odpoj.",
                    messages.ERROR,
                )
                return redirect(reverse("admin:accounts_profile_link_detail",
                                        args=[account.pk]))
            profile, _ = Profile.objects.get_or_create(user=account)
            profile.leaderboard_user = player
            profile.save(update_fields=["leaderboard_user"])

        # The leaderboard payload carries profile_username, so a fresh link
        # changes what /api/v1/leaderboard/ returns.
        from leaderboard.cache_config import invalidate_points_dependent_caches
        invalidate_points_dependent_caches()

        self.message_user(
            request,
            f"Účet {account.username} propojen s hráčem {player.name}.",
            messages.SUCCESS,
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
        """Surface the linking tool from the Profile changelist."""
        pending = matching.unlinked_accounts().count()
        extra_context = {
            **(extra_context or {}),
            "link_tool_url": reverse("admin:accounts_profile_link_list"),
            "link_tool_pending": pending,
        }
        if pending:
            self.message_user(request, format_html(
                'Nepropojených účtů: {} — <a href="{}">propojit</a>',
                pending, reverse("admin:accounts_profile_link_list"),
            ), messages.INFO)
        return super().changelist_view(request, extra_context)
