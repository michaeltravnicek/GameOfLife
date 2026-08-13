"""Run the account-deletion flow by hand, for a request that arrives by e-mail.

Members can delete themselves from the profile page; this is the same code
path for the case where someone writes in instead — GDPR gives them a month,
and "log in and click the button" is not always an answer they can act on.
"""
from django.contrib.auth.models import User as AuthUser
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.services import anonymize_account


class Command(BaseCommand):
    help = (
        "Delete an account's personal data and keep its points as an anonymous "
        "player. Identify the account by username or e-mail."
    )

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="username or e-mail of the account")
        parser.add_argument(
            "--yes", action="store_true",
            help="skip the confirmation prompt (for scripted runs)",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"].strip()
        user = (
            AuthUser.objects.filter(username=identifier).first()
            or AuthUser.objects.filter(email__iexact=identifier).first()
        )
        if user is None:
            raise CommandError(f"Žádný účet pro „{identifier}“.")

        profile = getattr(user, "profile", None)
        lb_user = profile.leaderboard_user if profile else None
        points = lb_user.usertoevent_set.count() if lb_user else 0

        self.stdout.write(f"Účet:  {user.username} <{user.email or 'bez e-mailu'}>")
        self.stdout.write(
            f"Hráč:  {lb_user.name if lb_user else '— žádný —'}"
            f"{f' (#{lb_user.pk}, {points} účastí)' if lb_user else ''}"
        )
        self.stdout.write(
            "Smaže se účet, profil, fotky a lajky. Body a účast zůstanou "
            "anonymizované."
        )

        if not options["yes"]:
            # Irreversible and driven by someone else's request — worth one
            # deliberate keystroke.
            if input("Pokračovat? [napiš ANO]: ").strip() != "ANO":
                self.stdout.write(self.style.WARNING("Zrušeno, nic se nezměnilo."))
                return

        with transaction.atomic():
            anonymize_account(user)

        self.stdout.write(self.style.SUCCESS(
            f"Hotovo. {'Hráč #%s zůstal anonymní.' % lb_user.pk if lb_user else 'Účet neměl hráče.'}"
        ))
