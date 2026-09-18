from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from leaderboard.models import Season


class Command(BaseCommand):
    help = "Ensure a Season exists for the current calendar year and is marked active."

    def handle(self, *args, **options):
        year = date.today().year
        with transaction.atomic():
            # Created inactive on purpose: last year's season is still active
            # on the first run of January, and the DB allows only one.
            season, created = Season.objects.get_or_create(
                name=str(year),
                defaults={
                    "start_date": date(year, 1, 1),
                    "end_date": date(year, 12, 31),
                },
            )
            was_active = season.is_active
            season.activate()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created season {season.name}"))
        elif not was_active:
            self.stdout.write(self.style.SUCCESS(f"Activated season {season.name}"))
        else:
            self.stdout.write(f"Season {season.name} already active")
