"""Event list querying + official image uploads for the API."""
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from leaderboard.image_utils import validate_upload
from leaderboard.models import Event, ImageToEvent

# Columns the events list / home cards actually serialize. The logo lives on the
# linked badge now, so its columns are pulled through the select_related below —
# leaving them out of `only()` would cost one query per card.
EVENTS_LIST_FIELDS = (
    "id", "slug", "name", "description", "place",
    "date", "time_tbd", "points", "image", "capacity", "category_id",
    "visible_to_users", "visible_to_close",
    "badge_id", "badge__image", "badge__image_scale",
)


def visible_event_or_404(request, slug, queryset=None):
    """The event at `slug`, or Http404 when this viewer may not see it.

    Hidden events: admin sees everything; close + photographer see only the
    ones explicitly flagged visible_to_close; everyone else gets 404. Every
    endpoint that acts on one event goes through here so a draft cannot
    collect RSVPs, feedback or check-ins before it is published.
    """
    from accounts.permissions import is_admin, is_close_or_above

    event = get_object_or_404(queryset if queryset is not None else Event, slug=slug)
    if not event.visible_to_users:
        allowed = is_admin(request.user) or (
            is_close_or_above(request.user) and event.visible_to_close
        )
        if not allowed:
            raise Http404("Akce nenalezena.")
    return event


def list_events(period="all", city="", category="", q="", season=None,
                offset=0, limit=30, include_hidden=False, include_close_preview=False):
    """Filtered, ordered events page. Returns ``(page_queryset, total_count)``.

    `include_hidden=False` (the default) hides events with
    ``visible_to_users=False`` — pass True only for admin/photographer views.
    `include_close_preview=True` ALSO surfaces events flagged
    ``visible_to_close=True`` for users with role 'close' (early peek).
    """
    qs = (
        Event.objects
        .select_related("category", "badge")
        .only(*EVENTS_LIST_FIELDS)
        # nulls_last: Postgres sorts NULL first on DESC, which would pin
        # dateless events to the top of the list.
        .order_by(F("date").desc(nulls_last=True))
    )
    if not include_hidden:
        if include_close_preview:
            qs = qs.filter(Q(visible_to_users=True) | Q(visible_to_close=True))
        else:
            qs = qs.filter(visible_to_users=True)

    now = timezone.now()
    if period == "upcoming":
        qs = qs.filter(date__gte=now).order_by("date")
    elif period == "past":
        qs = qs.filter(date__lt=now)

    if season is not None:
        qs = qs.filter(date__date__gte=season.start_date, date__date__lte=season.end_date)
    if city:
        qs = qs.filter(place__iexact=city)
    if category:
        try:
            qs = qs.filter(category_id=int(category))
        except ValueError:
            qs = qs.filter(category__name__iexact=category)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    total = qs.count()
    return qs[offset:offset + limit], total


def add_event_images(event, files):
    """Attach official images to an event. Each is validated, then downscaled
    on save (1024×1024, q75). Raises ValueError on a bad upload.
    """
    created = []
    for upload in files:
        validate_upload(upload)
        created.append(ImageToEvent.objects.create(event=event, image=upload))
    return created
