"""Fold Event.logo into Badge — one artwork row per distinct image.

Events carried their own `logo` ImageField, so the same file was re-uploaded for
every edition: 135 files under media/event_logos/ were only 7 distinct images,
one of them stored 72 times. Badge already existed for exactly this ("the
artwork lives here once and events point at it"), it just ran alongside `logo`
instead of replacing it.

This migration groups events by the *content* of their logo (MD5, not filename —
duplicates differ only by Django's collision suffix, `logo_66oY4ex.svg`), creates
one Badge per distinct image, and repoints every event at it.

⚠ Attaching a badge to an event is not cosmetic: `leaderboard.signals`
awards the badge to everyone with attendance on that event, on every
UserToEvent save. So after this migration the next Sheets sync hands every past
attendee the badges for the events they went to. That is intended — logo and
collectible emblem are deliberately the same thing now.

Files are NOT moved. Badge.image stores the existing `event_logos/...` key
verbatim; `upload_to` only governs where *new* uploads land, so the bytes stay
exactly where they are and no URL changes. Cleaning up the 128 orphaned
duplicate files on disk is a separate, manual step.

Irreversible: the per-event artwork cannot be reconstructed once N events share
one row.
"""
import hashlib
import logging

import django.db.models.deletion
from django.db import migrations, models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.text import slugify

logger = logging.getLogger(__name__)


def _digest(field_file):
    """MD5 of a stored file, or None when it can't be read.

    Goes through the storage API rather than a filesystem path, so this works
    the same on local disk and on S3/R2 (where `.path` raises).
    """
    try:
        with field_file.storage.open(field_file.name, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()
    except Exception:  # noqa: BLE001 — a missing file must not abort the deploy
        logger.warning("logo→badge: cannot read %r, falling back to its name",
                       field_file.name)
        return None


def _unique_slug(Badge, name):
    """Badge.save() builds the slug, but historical models have no methods."""
    base = slugify(name) or "odznak"
    slug, n = base, 2
    while Badge.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def logos_to_badges(apps, schema_editor):
    Badge = apps.get_model("leaderboard", "Badge")
    Event = apps.get_model("leaderboard", "Event")

    # Oldest first, so the badge inherits the name of the event that introduced
    # the artwork rather than an arbitrary later edition.
    events = (Event.objects
              .exclude(logo="")
              .filter(logo__isnull=False)
              .order_by("date", "id"))

    badge_by_key = {}
    for event in events:
        # Fall back to the stored name when the file is unreadable: a broken
        # reference then gets its own badge instead of silently merging with
        # every other broken one.
        key = _digest(event.logo) or f"name:{event.logo.name}"

        badge = badge_by_key.get(key)
        if badge is None:
            badge = Badge.objects.create(
                name=event.name or "Odznak",
                slug=_unique_slug(Badge, event.name or "odznak"),
                image=event.logo.name,          # same key, file stays put
                image_scale=event.logo_scale or 1.0,
                description="",
            )
            badge_by_key[key] = badge

        # An event that already had a badge keeps it — an explicitly assigned
        # emblem outranks one derived from artwork.
        if event.badge_id is None:
            event.badge_id = badge.pk
            event.save(update_fields=["badge"])

    logger.info("logo→badge: %d events collapsed into %d badges",
                events.count(), len(badge_by_key))


def irreversible(apps, schema_editor):
    raise RuntimeError(
        "0024 cannot be reversed: several events now share one Badge row, so "
        "there is no per-event logo left to restore. Recover from a database "
        "snapshot instead — the image files themselves were never moved."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0023_badge_event_badge_userbadge"),
    ]

    # Data only. Dropping the columns lives in 0025 because Postgres refuses to
    # ALTER a table that still has pending trigger events from writes earlier in
    # the same transaction ("cannot ALTER TABLE ... because it has pending
    # trigger events") -- and this RunPython writes Event.badge_id.
    operations = [
        migrations.AddField(
            model_name="badge",
            name="image_scale",
            field=models.FloatField(
                default=1.0,
                help_text="Zvětšení/zmenšení obrázku při zobrazení. 1.0 = beze změny.",
                validators=[MinValueValidator(0.1), MaxValueValidator(5.0)],
            ),
        ),
        # Must run while Event.logo/logo_scale still exist.
        migrations.RunPython(logos_to_badges, irreversible),
    ]
