from django.core.management.base import BaseCommand, CommandError
from leaderboard.models import Event, EventRSVP, UserToEvent, User


class Command(BaseCommand):
    help = "Award points to all users who RSVP'd to an event"

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=int, help="Event ID to award points for")

    def handle(self, *args, **options):
        event_id = options["event_id"]

        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            raise CommandError(f"Event with ID {event_id} does not exist")

        rsvps = EventRSVP.objects.filter(event=event).select_related("auth_user__profile__leaderboard_user")
        awarded = 0
        skipped = 0

        for rsvp in rsvps:
            lb_user = rsvp.auth_user.profile.leaderboard_user if hasattr(rsvp.auth_user, 'profile') else None
            if lb_user is None:
                skipped += 1
                continue

            _, created = UserToEvent.objects.get_or_create(
                user=lb_user,
                event=event,
                defaults={"points": event.points}
            )
            if created:
                awarded += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Event '{event.name}': {awarded} points awarded, {skipped} skipped"
            )
        )
