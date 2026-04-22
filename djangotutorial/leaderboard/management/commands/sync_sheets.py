from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Sync leaderboard data from Google Sheets (run daily at 4 AM)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-all",
            action="store_true",
            help="Force full re-sync regardless of last update time",
        )

    def handle(self, *args, **options):
        from datetime import timedelta
        from leaderboard.models import LastUpdate
        from datetime import datetime
        from django.utils.timezone import utc

        force_all = options["force_all"]
        now = timezone.now()

        last_update_obj, _ = LastUpdate.objects.get_or_create(
            pk=1,
            defaults={
                "last_update": datetime.fromtimestamp(0, tz=utc),
                "last_complete_update": None,
            },
        )

        # Skip if already ran today (unless forced)
        if not force_all and last_update_obj.last_complete_update:
            if last_update_obj.last_complete_update.date() == now.date():
                self.stdout.write("Already synced today, skipping.")
                return

        run_all = force_all or last_update_obj.last_complete_update is None

        self.stdout.write(f"Starting sync (run_all={run_all})...")
        try:
            from leaderboard.tasks import main
            from django.db import connections
            for conn in connections.all():
                conn.close()
            main(run_all)
            last_update_obj.last_update = now
            last_update_obj.last_complete_update = now
            last_update_obj.save()
            self.stdout.write(self.style.SUCCESS("Sync complete."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Sync failed: {e}"))
            raise
