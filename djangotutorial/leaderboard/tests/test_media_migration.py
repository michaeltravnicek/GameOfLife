"""migrate_media_to_s3 copies MEDIA_ROOT into object storage without data loss.

The command runs once, by hand, against the only surviving copy of every user
upload -- so the properties worth testing are the destructive-mistake ones: does
it refuse to run misconfigured, does it preserve the exact storage keys the
database already points at, and does it leave the local files alone.
"""
import os
import tempfile
from io import BytesIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from unittest import mock


class _FakeS3Storage:
    """Minimal stand-in for S3Storage: records what was written, under what key."""

    def __init__(self):
        self.saved = {}

    def exists(self, key):
        return key in self.saved

    def save(self, key, content):
        self.saved[key] = content.read()
        return key

    def delete(self, key):
        self.saved.pop(key, None)


# Credentials present. Whether the *app* is serving from S3 is a separate flag —
# during the cutover it deliberately is not.
S3_OPTIONS = {"bucket_name": "gameofyolo-media-test"}


class MigrateMediaToS3Tests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media_root = self.tmp.name

        # An original plus the .mobile.webp sibling that image_utils writes next
        # to it. The sibling is referenced by URL convention, not by any model
        # field, so it is the thing a model-driven copy would silently drop.
        os.makedirs(os.path.join(self.media_root, "event_images"))
        self._write("event_images/party.jpg", b"original-bytes")
        self._write("event_images/party.jpg.mobile.webp", b"variant-bytes")

        self.storage = _FakeS3Storage()

    def _write(self, rel_path, data):
        path = os.path.join(self.media_root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def _run(self, media_s3_enabled=False, **kwargs):
        """Run the command with credentials configured.

        `media_s3_enabled` defaults to False on purpose: the whole point of the
        two-phase cutover is that the copy happens while the app is still serving
        from local disk.
        """
        with override_settings(
            MEDIA_ROOT=self.media_root,
            MEDIA_S3_OPTIONS=S3_OPTIONS,
            MEDIA_S3_ENABLED=media_s3_enabled,
        ):
            with mock.patch(
                "leaderboard.management.commands.migrate_media_to_s3.get_target_storage",
                return_value=self.storage,
            ):
                call_command("migrate_media_to_s3", **kwargs)

    # --- the misconfiguration guard --------------------------------------

    def test_refuses_to_run_without_credentials(self):
        # Without this guard the command would have nowhere to upload to and
        # would report success anyway — the worst outcome: it looks done.
        with override_settings(MEDIA_ROOT=self.media_root, MEDIA_S3_OPTIONS=None):
            with self.assertRaises(CommandError) as ctx:
                call_command("migrate_media_to_s3", dry_run=True)
        self.assertIn("MEDIA_S3_", str(ctx.exception))

    def test_runs_while_the_app_is_still_serving_from_local_disk(self):
        """The cutover-order property, stated as a test.

        Copying must be possible *before* the S3 backend goes live. If this ever
        required MEDIA_S3_ENABLED=1, every image on the site would 404 for the
        duration of the upload, because FileField URLs repoint at the bucket the
        instant the backend switches.
        """
        self._run(media_s3_enabled=False)
        self.assertIn("event_images/party.jpg", self.storage.saved)

    # --- the copy ---------------------------------------------------------

    def test_uploads_under_keys_relative_to_media_root(self):
        # The key must equal what FileField stored, or existing rows break.
        self._run()
        self.assertIn("event_images/party.jpg", self.storage.saved)
        self.assertEqual(self.storage.saved["event_images/party.jpg"], b"original-bytes")

    def test_carries_the_mobile_webp_variants(self):
        self._run()
        self.assertIn("event_images/party.jpg.mobile.webp", self.storage.saved)

    def test_dry_run_writes_nothing(self):
        self._run(dry_run=True)
        self.assertEqual(self.storage.saved, {})

    def test_never_deletes_local_files(self):
        self._run()
        self.assertTrue(os.path.exists(os.path.join(self.media_root, "event_images/party.jpg")))

    # --- idempotence ------------------------------------------------------

    def test_rerun_skips_existing_keys(self):
        self._run()
        self.storage.saved["event_images/party.jpg"] = b"REMOTE-WINS"
        self._run()
        # Skipped, not re-uploaded: an interrupted run is safe to repeat.
        self.assertEqual(self.storage.saved["event_images/party.jpg"], b"REMOTE-WINS")

    def test_force_overwrites_existing_keys(self):
        self._run()
        self.storage.saved["event_images/party.jpg"] = b"CORRUPT"
        self._run(force=True)
        self.assertEqual(self.storage.saved["event_images/party.jpg"], b"original-bytes")

    # --- verify -----------------------------------------------------------

    def test_verify_passes_once_everything_is_uploaded(self):
        self._run()
        self._run(verify=True)  # must not raise

    def test_verify_fails_when_a_file_is_missing_remotely(self):
        self._run()
        del self.storage.saved["event_images/party.jpg.mobile.webp"]
        with self.assertRaises(CommandError):
            self._run(verify=True)
