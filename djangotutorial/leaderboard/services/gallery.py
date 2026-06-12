"""Combined gallery (official + user photos) with bounded merge-pagination."""
from datetime import datetime, timezone as _tz

from django.db.models import F

from leaderboard.image_utils import validate_upload, variant_url
from leaderboard.models import Event, ImageToEvent, UserPhoto

# Sort key for photos with no event date — they sink to the bottom.
_SORT_FALLBACK = datetime.min.replace(tzinfo=_tz.utc)


def create_user_photo(user, image, *, event_slug="", caption=""):
    """Create a community gallery photo for `user`.

    `validate_upload` guards size/type; `UserPhoto.save()` downscales the stored
    file (1600×1600, q80). Raises ValueError for a bad image and LookupError for
    an unknown event slug.
    """
    validate_upload(image)
    event = None
    if event_slug:
        event = Event.objects.filter(slug=event_slug).first()
        if event is None:
            raise LookupError("Akce nenalezena.")
    return UserPhoto.objects.create(
        auth_user=user,
        event=event,
        image=image,
        caption=(caption or "").strip()[:255],
    )


def gallery_page(offset, limit, request, season=None):
    """Merged, date-desc photo page. Returns ``(photos, total_count)``.

    Both sources are date-ordered in the DB, so we pull only ``offset+limit``
    rows from each, merge, and slice — bounded memory instead of loading every
    photo. ``request`` is used to build absolute media URLs. When ``season`` is
    given, only photos whose event falls inside the season window are included.
    """
    upper = offset + limit

    official = (
        ImageToEvent.objects
        .select_related("event_id")
        .exclude(image="")
        .filter(image__isnull=False)
        .only("image", "event_id__name", "event_id__slug", "event_id__date")
        .order_by("-event_id__date")
    )
    user_photos = (
        UserPhoto.objects
        .select_related("auth_user", "event")
        .exclude(image="")
        .filter(image__isnull=False)
        .only("image", "event__name", "event__slug", "event__date",
              "auth_user__first_name", "auth_user__last_name", "auth_user__username")
        .order_by(F("event__date").desc(nulls_last=True))
    )

    if season is not None:
        official = official.filter(
            event_id__date__date__gte=season.start_date,
            event_id__date__date__lte=season.end_date,
        )
        user_photos = user_photos.filter(
            event__date__date__gte=season.start_date,
            event__date__date__lte=season.end_date,
        )

    total = official.count() + user_photos.count()

    photos = []
    for img in official[:upper]:
        photos.append({
            "url": request.build_absolute_uri(img.image.url),
            "url_mobile": variant_url(img.image, request),
            "event_name": img.event_id.name if img.event_id else "",
            "event_slug": img.event_id.slug if img.event_id else "",
            "event_date": img.event_id.date if img.event_id else None,
            "is_user_photo": False,
            "uploaded_by": "",
        })
    for up in user_photos[:upper]:
        photos.append({
            "url": request.build_absolute_uri(up.image.url),
            "url_mobile": variant_url(up.image, request),
            "event_name": up.event.name if up.event else "",
            "event_slug": up.event.slug if up.event else "",
            "event_date": up.event.date if up.event else None,
            "is_user_photo": True,
            "uploaded_by": up.auth_user.get_full_name() or up.auth_user.username,
        })

    photos.sort(key=lambda p: p["event_date"] or _SORT_FALLBACK, reverse=True)
    return photos[offset:upper], total
