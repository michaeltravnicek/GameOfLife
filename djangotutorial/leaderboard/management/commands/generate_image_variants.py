"""Backfill mobile WebP variants for already-uploaded media.

New uploads get their variant in the model ``save()``; this one-off command
produces variants for images that predate that change. Idempotent — safe to
re-run (an existing, up-to-date variant is skipped).

    python3 manage.py generate_image_variants
    python3 manage.py generate_image_variants --force   # regenerate even if present
"""
import os

from django.core.management.base import BaseCommand

from accounts.models import Profile
from leaderboard.image_utils import make_webp_variant, variant_name
from leaderboard.models import Event, ImageToEvent, UserPhoto

# (queryset, field name, make_webp_variant kwargs) — mirrors each model's save().
TARGETS = [
    (Event.objects.exclude(image="").filter(image__isnull=False), "image", {}),
    (ImageToEvent.objects.exclude(image="").filter(image__isnull=False), "image", {}),
    (UserPhoto.objects.exclude(image="").filter(image__isnull=False), "image", {}),
    (Profile.objects.exclude(photo="").filter(photo__isnull=False), "photo",
     {"max_width": 200, "quality": 60}),
]


class Command(BaseCommand):
    help = "Generate mobile WebP variants for existing uploaded images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Regenerate even when a variant already exists.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        made = skipped = missing = 0

        for qs, field_name, kwargs in TARGETS:
            for obj in qs.iterator():
                field = getattr(obj, field_name)
                path = getattr(field, "path", None)
                if not path or not os.path.exists(path):
                    missing += 1
                    continue
                if not force and os.path.exists(variant_name(path)):
                    skipped += 1
                    continue
                make_webp_variant(field, **kwargs)
                made += 1
                self.stdout.write(f"  ✓ {field.name}")

        self.stdout.write(self.style.SUCCESS(
            f"Done — generated {made}, skipped {skipped}, missing files {missing}."
        ))
