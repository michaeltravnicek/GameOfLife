"""Combined gallery (official + user photos) with bounded merge-pagination.

The page this builds is deliberately identical for every viewer, which is what
lets it be cached at the edge. Who liked what is NOT in it -- that is one small
query behind `liked_photo_ids`, which the client overlays. See the note on
`gallery_page` for why the two were split.
"""
from datetime import datetime, timezone as _tz

from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth
from django.http import Http404

from leaderboard.image_utils import validate_upload, variant_url
from leaderboard.models import ImageToEvent, PhotoLike, UserPhoto
from leaderboard.privacy import public_handle
from leaderboard.services.events import visible_event_or_404

# Sort key for photos with no event date — they sink to the bottom.
_SORT_FALLBACK = datetime.min.replace(tzinfo=_tz.utc)


def create_user_photo(user, image, *, event_slug="", caption=""):
    """Create a community gallery photo for `user`.

    `validate_upload` guards size/type; `UserPhoto.save()` downscales the stored
    file (1600×1600, q80). Raises ValueError for a bad image and LookupError for
    an event slug that is unknown or hidden from `user`.
    """
    validate_upload(image)
    event = None
    if event_slug:
        try:
            event = visible_event_or_404(user, event_slug)
        except Http404:
            raise LookupError("Akce nenalezena.") from None
    return UserPhoto.objects.create(
        auth_user=user,
        event=event,
        image=image,
        caption=(caption or "").strip()[:255],
    )


def _sources(season=None, month=None):
    """The two photo querysets, filtered the same way, unordered and unsliced.

    ``month`` is ``(year, month)`` or ``"unknown"`` (photos whose event has no
    date, or no event at all). Months are taken in the server's time zone, the
    same one ``event_date`` is serialised in.
    """
    official = (
        ImageToEvent.objects
        .exclude(image="")
        # One page for every viewer, cached at the edge: published events only.
        .filter(image__isnull=False, event__visible_to_users=True)
    )
    user_photos = (
        UserPhoto.objects
        .exclude(image="")
        .filter(image__isnull=False)
        .filter(Q(event__isnull=True) | Q(event__visible_to_users=True))
    )
    filters = []
    if season is not None:
        filters.append(season.date_window())
    if month == "unknown":
        filters.append(Q(event__date__isnull=True))
    elif month is not None:
        year, mon = month
        filters.append(Q(event__date__year=year, event__date__month=mon))
    for q in filters:
        official = official.filter(q)
        user_photos = user_photos.filter(q)
    return official, user_photos


def gallery_months(season=None):
    """Every month that has photos, newest first, as ``[{month, count}]``.

    ``month`` is ``"YYYY-MM"``, or ``"unknown"`` (always last). Two grouped
    counts, so the page can lay out every month heading without loading a
    single photo.
    """
    counts = {}
    for qs in _sources(season):
        rows = (
            qs.annotate(m=TruncMonth("event__date"))
            .values("m")
            .annotate(n=Count("pk"))
            .order_by()
        )
        for row in rows:
            key = row["m"].strftime("%Y-%m") if row["m"] else "unknown"
            counts[key] = counts.get(key, 0) + row["n"]
    dated = sorted((k for k in counts if k != "unknown"), reverse=True)
    if "unknown" in counts:
        dated.append("unknown")
    return [{"month": k, "count": counts[k]} for k in dated]


def gallery_page(offset, limit, request, season=None, month=None):
    """Merged, date-desc photo page. Returns ``(photos, total_count)``.

    Both sources are date-ordered in the DB, so we pull only ``offset+limit``
    rows from each, merge, and slice — bounded memory instead of loading every
    photo. ``request`` is used to build absolute media URLs. ``season`` keeps
    photos whose event falls inside the season window; ``month`` narrows to one
    month (see ``_sources``).
    """
    upper = offset + limit

    official, user_photos = _sources(season, month)
    official = (
        official
        .select_related("event")
        .only("image", "event__name", "event__slug", "event__date")
        .order_by("-event__date")
    )
    user_photos = (
        user_photos
        .select_related("auth_user", "event")
        .only("image", "event__name", "event__slug", "event__date",
              "auth_user__first_name", "auth_user__last_name", "auth_user__username")
        # Counted in the same query rather than per photo: a 60-photo page would
        # otherwise issue 60 extra COUNT(*)s just to draw the hearts.
        .annotate(like_count=Count("likes"))
        .order_by(F("event__date").desc(nulls_last=True))
    )

    total = official.count() + user_photos.count()

    photos = []
    for img in official[:upper]:
        photos.append({
            # Official event photos carry no id and no like state: PhotoLike
            # hangs off UserPhoto, so there is nothing for a heart to point at.
            # `None` (not 0) is what tells the client "not likeable" apart from
            # "likeable, nobody has yet".
            "id": None,
            "url": request.build_absolute_uri(img.image.url),
            "url_mobile": variant_url(img.image, request, check_exists=False),
            "event_name": img.event.name if img.event else "",
            "event_slug": img.event.slug if img.event else "",
            "event_date": img.event.date if img.event else None,
            "is_user_photo": False,
            "uploaded_by": "",
            "like_count": None,
        })
    for up in user_photos[:upper]:
        photos.append({
            "id": up.pk,
            "url": request.build_absolute_uri(up.image.url),
            "url_mobile": variant_url(up.image, request, check_exists=False),
            "event_name": up.event.name if up.event else "",
            "event_slug": up.event.slug if up.event else "",
            "event_date": up.event.date if up.event else None,
            "is_user_photo": True,
            # Never fall back to the raw username — it's the e-mail for social
            # logins. Prefer a real name, then a safe handle, then a neutral label.
            "uploaded_by": (
                up.auth_user.get_full_name()
                or public_handle(up.auth_user.username)
                or "Hráč"
            ),
            "like_count": up.like_count,
        })

    photos.sort(key=lambda p: p["event_date"] or _SORT_FALLBACK, reverse=True)
    return photos[offset:upper], total


def liked_photo_ids(user):
    """Ids of the user photos ``user`` has liked, as a list.

    Kept out of the gallery payload on purpose: that page is edge-cached and
    identical for everyone, so a per-viewer flag in it would hand one visitor's
    likes to the next. This lives behind its own ``no-store`` endpoint and the
    client paints the hearts on top of the cached list.
    """
    if user is None or not user.is_authenticated:
        return []
    return list(
        PhotoLike.objects
        .filter(auth_user=user)
        .values_list("photo_id", flat=True)
    )
