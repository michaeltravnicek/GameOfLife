"""Backfill mobile WebP variants -- and, opt-in, convert originals to WebP.

New uploads are handled in each model's ``save()`` (convert, then variant); this
command applies the same treatment to images that predate those changes.

    python3 manage.py generate_image_variants                 # variants only
    python3 manage.py generate_image_variants --force         # regenerate variants
    python3 manage.py generate_image_variants --resize --dry-run   # preview
    python3 manage.py generate_image_variants --resize        # ALSO convert originals

``--resize`` is opt-in and IRREVERSIBLE: it re-encodes each original as WebP at
the limits ``save()`` uses, so the full-resolution upload is gone afterwards.
Back up MEDIA_ROOT first, and keep it off the automatic deploy path in build.sh
unless you've decided you never want the originals back.

It also **renames the stored file** (``foo.jpg`` -> ``foo.webp``) and writes the
new key back to the database row. Two consequences worth knowing:

  * Every affected image URL changes, so anything holding an old URL (a CDN
    cache, a shared link, a screenshot in a chat) stops resolving. Purge the
    Cloudflare cache afterwards.
  * Re-encoding an already-lossy JPEG stacks a second generation of loss. It is
    modest, but the original is not recoverable once this has run.

Without ``--resize`` the command behaves exactly as before -- variants only,
nothing destructive.
"""
from django.apps import apps
from django.core.management.base import BaseCommand

from leaderboard.image_utils import (
    UPLOAD_LIMITS, make_webp_variant, needs_processing, process_upload,
    variant_name,
)


def targets():
    """(queryset, field, (w, h, cap), variant_kwargs) for every registered field.

    Derived from image_utils.UPLOAD_LIMITS rather than listed again here. The
    limits used to be duplicated in both places, which meant a change to a
    model's save() silently left the backfill converting to the old dimensions --
    and nothing failed, the files just came out wrong.
    """
    for key, (max_width, max_height, cap, variant_kwargs) in UPLOAD_LIMITS.items():
        app_label, model_name, field_name = key.split(".")
        model = apps.get_model(app_label, model_name)
        queryset = (model.objects
                    .exclude(**{field_name: ""})
                    .filter(**{f"{field_name}__isnull": False}))
        yield queryset, field_name, (max_width, max_height, cap), variant_kwargs


def _mb(num_bytes):
    return f"{num_bytes / (1024 * 1024):.1f} MB"


class Command(BaseCommand):
    help = ("Generate mobile WebP variants for existing images; "
            "optionally downscale oversized originals (--resize).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Regenerate variants even when one already exists.",
        )
        parser.add_argument(
            "--resize", action="store_true",
            help="Also convert originals to WebP under the cap, renaming the "
                 "stored file and updating the row (IRREVERSIBLE).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        do_resize = options["resize"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be written.\n"))

        made = skipped = missing = resized = 0
        saved_bytes = 0

        for qs, field_name, limits, variant_kwargs in targets():
            for obj in qs.iterator():
                field = getattr(obj, field_name)
                # Storage-abstracted so backfill runs against local disk or S3/R2.
                if not field.name or not field.storage.exists(field.name):
                    missing += 1
                    continue

                # Convert first: the variant must be derived from the final
                # original, exactly as in save().
                shrunk = False
                if do_resize and needs_processing(field, *limits):
                    before = field.storage.size(field.name)
                    old_name = field.name
                    if dry_run:
                        resized += 1
                        self.stdout.write(f"  ~ would convert {old_name} ({_mb(before)})")
                        continue
                    stored = process_upload(field, *limits)
                    if stored:
                        # process_upload moved the file; the row must follow it
                        # or the record points at a key that no longer exists.
                        field.name = stored
                        obj.__class__.objects.filter(pk=obj.pk).update(**{field_name: stored})
                    after = field.storage.size(field.name)
                    if after < before:
                        saved_bytes += before - after
                        resized += 1
                        shrunk = True
                        arrow = f"  ↓ {old_name}  {_mb(before)} → {_mb(after)}"
                        if stored:
                            arrow += f"  (→ {stored})"
                        self.stdout.write(arrow)

                if dry_run or variant_kwargs is None:
                    continue
                # A variant built from the pre-resize original is stale, so a
                # shrink always re-derives it.
                if not (force or shrunk) and field.storage.exists(variant_name(field.name)):
                    skipped += 1
                    continue
                make_webp_variant(field, **variant_kwargs)
                made += 1
                self.stdout.write(f"  ✓ {field.name}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nDry run — {resized} originals would be converted, "
                f"missing files {missing}."
            ))
            return

        summary = f"Done — generated {made}, skipped {skipped}, missing files {missing}."
        if do_resize:
            summary += f" Converted {resized} originals, freed {_mb(saved_bytes)}."
        self.stdout.write(self.style.SUCCESS(summary))
