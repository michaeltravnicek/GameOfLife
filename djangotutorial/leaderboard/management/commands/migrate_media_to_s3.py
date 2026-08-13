"""Copy everything under MEDIA_ROOT into the configured object storage.

Run this ONCE, during the cutover from local disk to S3/R2:

    # 1. set MEDIA_S3_* AND MEDIA_S3_ENABLED=0
    #    (credentials available; the app keeps serving from disk meanwhile)
    python3 manage.py migrate_media_to_s3 --dry-run     # see what would move
    python3 manage.py migrate_media_to_s3               # actually upload
    python3 manage.py migrate_media_to_s3 --verify      # confirm every file arrived
    # 2. set MEDIA_S3_ENABLED=1 and redeploy

The command uploads to the bucket described by MEDIA_S3_*, NOT to whatever
`default_storage` happens to be. That is the whole reason the cutover can be done
without downtime: the database stores keys relative to MEDIA_ROOT and FileField
resolves them against the active backend, so switching backends instantly
repoints every existing image URL at the bucket. Copy first, switch second.

This command never deletes anything locally. Delete the source files by hand once
--verify passes and you have seen images loading from the CDN.

Idempotent: a key that already exists in the bucket is skipped, so an interrupted
run can simply be repeated. Use --force to overwrite (only useful if a previous
run uploaded corrupt or truncated objects).

The walk is filesystem-based rather than model-based on purpose. Model fields
would miss the `.mobile.webp` siblings that image_utils.make_webp_variant writes
next to each original -- those are referenced by URL convention, not by a
database column, so a model-driven copy would silently leave every mobile
variant behind and the site would serve full-size images to phones.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _mb(num_bytes):
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def get_target_storage():
    """The S3/R2 bucket to upload into, built from MEDIA_S3_* directly.

    Deliberately not `default_storage`: during the cutover the active media
    backend is still the local filesystem (MEDIA_S3_ENABLED=0), and using it here
    would copy MEDIA_ROOT onto itself while reporting success.
    """
    options = getattr(settings, "MEDIA_S3_OPTIONS", None)
    if not options:
        raise CommandError(
            "MEDIA_S3_* environment variables are not set, so there is nowhere to "
            "upload to.\nSet MEDIA_S3_BUCKET / _ENDPOINT / _ACCESS_KEY / _SECRET_KEY "
            "(and MEDIA_S3_ENABLED=0 until the copy is verified) first."
        )
    from storages.backends.s3 import S3Storage
    return S3Storage(**options)


class Command(BaseCommand):
    help = "Upload local MEDIA_ROOT files to the configured object storage (S3/R2)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="List what would be uploaded without writing anything.")
        parser.add_argument(
            "--force", action="store_true",
            help="Re-upload keys that already exist in the bucket.")
        parser.add_argument(
            "--verify", action="store_true",
            help="Upload nothing; just report which local files are missing remotely.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        verify = options["verify"]

        media_root = str(settings.MEDIA_ROOT)
        if not os.path.isdir(media_root):
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        # Raises if the credentials are missing — the one mistake that would
        # otherwise look like a successful no-op.
        storage = get_target_storage()
        self.stdout.write(
            f"Source: {media_root}\n"
            f"Target: {settings.MEDIA_S3_OPTIONS['bucket_name']}"
            f" (active media backend: "
            f"{'S3' if settings.MEDIA_S3_ENABLED else 'local disk'})\n"
        )

        local_files = []
        for dirpath, _dirnames, filenames in os.walk(media_root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                # The storage key is the path relative to MEDIA_ROOT, which is
                # exactly what FileField stores in the database — so existing
                # rows keep resolving without a data migration.
                key = os.path.relpath(abs_path, media_root).replace(os.sep, "/")
                local_files.append((abs_path, key))

        if not local_files:
            self.stdout.write(self.style.WARNING(f"No files found under {media_root}."))
            return

        uploaded = skipped = missing = failed = 0
        total_bytes = 0

        for abs_path, key in sorted(local_files, key=lambda pair: pair[1]):
            try:
                exists = storage.exists(key)
            except Exception as exc:  # noqa: BLE001 -- report and continue
                self.stderr.write(self.style.ERROR(f"  ! {key}: cannot check ({exc})"))
                failed += 1
                continue

            if verify:
                if exists:
                    skipped += 1
                else:
                    missing += 1
                    self.stdout.write(self.style.ERROR(f"  MISSING {key}"))
                continue

            if exists and not force:
                skipped += 1
                continue

            size = os.path.getsize(abs_path)
            if dry_run:
                self.stdout.write(f"  would upload {key} ({_mb(size)})")
                uploaded += 1
                total_bytes += size
                continue

            try:
                if exists and force:
                    storage.delete(key)
                with open(abs_path, "rb") as fh:
                    # _save is bypassed by save()'s name-collision suffixing, which
                    # we explicitly do NOT want here: the key must stay identical
                    # to what the database already points at.
                    storage.save(key, fh)
            except Exception as exc:  # noqa: BLE001 -- one bad file shouldn't abort
                self.stderr.write(self.style.ERROR(f"  ! {key}: {exc}"))
                failed += 1
                continue

            uploaded += 1
            total_bytes += size
            self.stdout.write(f"  {key} ({_mb(size)})")

        self.stdout.write("")
        if verify:
            summary = f"Verify: {skipped} present remotely, {missing} MISSING, {failed} unreadable."
            style = self.style.SUCCESS if (missing == 0 and failed == 0) else self.style.ERROR
            self.stdout.write(style(summary))
            if missing:
                raise CommandError("Some files are not in the bucket — re-run without --verify.")
            return

        verb = "Would upload" if dry_run else "Uploaded"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {uploaded} file(s), {_mb(total_bytes)}. "
            f"Skipped {skipped} already present. {failed} failed."
        ))
        if failed:
            raise CommandError(f"{failed} file(s) failed to upload.")
        if not dry_run:
            self.stdout.write(
                "Next: run with --verify, load a few images from the site, and only "
                "then delete MEDIA_ROOT. Nothing local was removed."
            )
