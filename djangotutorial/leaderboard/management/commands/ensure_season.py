from datetime import date

from django.core.management.base import BaseCommand

from leaderboard.models import Season


class Command(BaseCommand):
    help = "Ensure a Season exists for the current calendar year and is marked active."

    def handle(self, *args, **options):
        year = date.today().year
        season, created = Season.objects.get_or_create(
            name=str(year),
            defaults={
                "start_date": date(year, 1, 1),
                "end_date": date(year, 12, 31),
                "is_active": True,
            },
        )
        if not season.is_active:
            Season.objects.exclude(pk=season.pk).update(is_active=False)
            season.is_active = True
            season.save(update_fields=["is_active"])
            self.stdout.write(self.style.SUCCESS(f"Activated season {season.name}"))
        elif created:
            self.stdout.write(self.style.SUCCESS(f"Created season {season.name}"))
        else:
            self.stdout.write(f"Season {season.name} already active")
