from django.core.management.base import BaseCommand

from leaderboard.models import Event
from leaderboard.utils import parse_event_date_from_name


class Command(BaseCommand):
    help = (
        "Fix sheet-synced events whose date is the sync timestamp instead of "
        "the real event date (parsed from the event name). Dry-run by default; "
        "pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the parsed dates.")

    def handle(self, *args, **options):
        apply = options["apply"]
        changed = 0
        # Only sheet-created events — manually created events got a real date
        # in the create form and must not be touched. `sheet_id` is "" (not
        # NULL) on those, so the filter has to be on the empty string.
        for event in Event.objects.exclude(sheet_id="").order_by("id"):
            parsed = parse_event_date_from_name(event.name)
            current = event.date.date() if event.date else None
            if parsed is None or parsed.date() == current:
                continue
            self.stdout.write(f"{event.id:4}  {event.name!r}: {current} -> {parsed.date()}")
            if apply:
                event.date = parsed
                event.save(update_fields=["date"])
            changed += 1

        verb = "updated" if apply else "would update (dry run, use --apply)"
        self.stdout.write(self.style.SUCCESS(f"{changed} events {verb}"))
        if apply and changed:
            # Event dates feed season bucketing → leaderboard/stat caches.
            from leaderboard.cache_config import invalidate_points_dependent_caches
            invalidate_points_dependent_caches()
