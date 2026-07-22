"""Backfill mobile WebP variants -- and, opt-in, downscale oversized originals.

New uploads are handled in each model's ``save()`` (resize, then variant); this
command applies the same treatment to images that predate those changes.

    python3 manage.py generate_image_variants                 # variants only
    python3 manage.py generate_image_variants --force         # regenerate variants
    python3 manage.py generate_image_variants --resize --dry-run   # preview
    python3 manage.py generate_image_variants --resize        # ALSO shrink originals

``--resize`` is opt-in and IRREVERSIBLE: it rewrites the stored file in place at
the same limits ``save()`` uses, so the full-resolution upload is gone
afterwards. Back up MEDIA_ROOT first, and keep it off the automatic deploy path
in build.sh unless you've decided you never want the originals back.

Without ``--resize`` the command behaves exactly as before -- variants only,
nothing destructive.
"""
import os

from django.core.management.base import BaseCommand

from accounts.models import Profile
from leaderboard.image_utils import (
    make_webp_variant, needs_resize, resize_image, variant_name,
)
from leaderboard.models import Event, ImageToEvent, UserPhoto

# (queryset, field name, resize_image kwargs, make_webp_variant kwargs).
# Mirrors each model's save() — keep the limits in sync with it.
TARGETS = [
    (Event.objects.exclude(image="").filter(image__isnull=False), "image",
     {"max_width": 1200, "max_height": 1200, "quality": 85}, {}),
    (ImageToEvent.objects.exclude(image="").filter(image__isnull=False), "image",
     {"max_width": 1024, "max_height": 1024, "quality": 75}, {}),
    (UserPhoto.objects.exclude(image="").filter(image__isnull=False), "image",
     {"max_width": 1600, "max_height": 1600, "quality": 80}, {}),
    (Profile.objects.exclude(photo="").filter(photo__isnull=False), "photo",
     {"max_width": 400, "max_height": 400, "quality": 85},
     {"max_width": 200, "quality": 60}),
]


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
            help="Also downscale oversized originals in place (IRREVERSIBLE).",
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

        for qs, field_name, resize_kwargs, variant_kwargs in TARGETS:
            for obj in qs.iterator():
                field = getattr(obj, field_name)
                path = getattr(field, "path", None)
                if not path or not os.path.exists(path):
                    missing += 1
                    continue

                # Resize first: the variant must be derived from the final
                # original, exactly as in save().
                shrunk = False
                if do_resize and needs_resize(
                    path,
                    resize_kwargs["max_width"],
                    resize_kwargs["max_height"],
                ):
                    before = os.path.getsize(path)
                    if dry_run:
                        resized += 1
                        self.stdout.write(f"  ~ would resize {field.name} ({_mb(before)})")
                        continue
                    resize_image(field, **resize_kwargs)
                    after = os.path.getsize(path)
                    if after < before:
                        saved_bytes += before - after
                        resized += 1
                        shrunk = True
                        self.stdout.write(
                            f"  ↓ {field.name}  {_mb(before)} → {_mb(after)}")

                if dry_run:
                    continue
                # A variant built from the pre-resize original is stale, so a
                # shrink always re-derives it.
                if not (force or shrunk) and os.path.exists(variant_name(path)):
                    skipped += 1
                    continue
                make_webp_variant(field, **variant_kwargs)
                made += 1
                self.stdout.write(f"  ✓ {field.name}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nDry run — {resized} originals would be resized, "
                f"missing files {missing}."
            ))
            return

        summary = f"Done — generated {made}, skipped {skipped}, missing files {missing}."
        if do_resize:
            summary += f" Resized {resized} originals, freed {_mb(saved_bytes)}."
        self.stdout.write(self.style.SUCCESS(summary))
