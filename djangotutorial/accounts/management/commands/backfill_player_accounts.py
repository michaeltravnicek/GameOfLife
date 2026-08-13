"""Give a leaderboard player to accounts that registered before we made one.

`ensure_leaderboard_user` runs at signup, so new accounts are fine. Accounts
created before it existed still have `profile.leaderboard_user = None`, and an
account without a player cannot check in at all (leaderboard/checkin.py). Run
once after deploying; it is idempotent, so running it again is harmless.

The e-mail rule is the same as at signup: an archive player carrying this
address is adopted rather than duplicated. `--dry-run` prints what would happen
and writes nothing -- worth doing first, because adoption is the step that hands
somebody an existing history.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.matching import accounts_without_player
from accounts.services import ensure_leaderboard_user
from leaderboard.models import User as LeaderboardUser


class Command(BaseCommand):
    help = "Create (or adopt) a LeaderboardUser for every account that lacks one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        accounts = list(accounts_without_player())
        if not accounts:
            self.stdout.write(self.style.SUCCESS("Každý účet už má hráče."))
            return

        created = adopted = 0
        for account in accounts:
            email = (account.email or "").strip().lower()
            existing = (
                LeaderboardUser.all_objects.filter(email__iexact=email).first()
                if email else None
            )
            if dry_run:
                verb = "PŘEVEZME" if existing else "založí"
                target = existing.name if existing else (
                    account.get_full_name().strip() or account.username)
                self.stdout.write(f"{account.username}: {verb} hráče „{target}“")
                continue

            with transaction.atomic():
                player = ensure_leaderboard_user(account)
            if existing is not None and player.pk == existing.pk:
                adopted += 1
                self.stdout.write(self.style.WARNING(
                    f"{account.username} převzal archivního hráče „{player.name}“ "
                    f"podle e-mailu."
                ))
            else:
                created += 1

        if dry_run:
            self.stdout.write(f"\n(dry run) dotčených účtů: {len(accounts)}")
            return
        self.stdout.write(self.style.SUCCESS(
            f"Hotovo: {created} nových hráčů, {adopted} převzatých z archivu."
        ))
