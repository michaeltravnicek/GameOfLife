"""The guard against forgetting: every image field must be registered.

An image field that nobody wired up does not fail — it quietly stores the
original at full size. Nothing errors, no test goes red, and the first symptom
is a 10 MB file on the CDN months later. That is exactly how the four
multi-megabyte JPEGs in media/event_images/ got there.

So the wiring is data, not five copies of the same code: image_utils.UPLOAD_LIMITS
lists every field, model save() and the backfill command both read it, and the
tests below fail the moment the project grows a field that is missing from it.
"""
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import TestCase

from leaderboard import image_utils
from leaderboard.image_utils import UPLOAD_EXEMPT, UPLOAD_LIMITS, limits_for

# Only our own apps. Third-party packages bring their own file fields and are
# not ours to process.
OUR_APPS = {"leaderboard", "accounts"}


def project_file_fields():
    """Every FileField/ImageField declared by our own models."""
    found = []
    for model in apps.get_models():
        if model._meta.app_label not in OUR_APPS:
            continue
        for field in model._meta.get_fields():
            if isinstance(field, models.FileField):  # ImageField subclasses it
                found.append(
                    (f"{model._meta.app_label}.{model._meta.object_name}.{field.name}",
                     model, field.name)
                )
    return found


class ImageFieldCoverageTests(TestCase):
    def test_every_image_field_is_registered(self):
        """Add an ImageField, add a line to UPLOAD_LIMITS. This is the reminder."""
        missing = sorted(
            key for key, _model, _field in project_file_fields()
            if key not in UPLOAD_LIMITS and key not in UPLOAD_EXEMPT
        )
        self.assertEqual(missing, [], (
            "These image fields have no entry in image_utils.UPLOAD_LIMITS, so "
            "uploads to them would be stored at full size, in their original "
            "format, with no size cap:\n  " + "\n  ".join(missing) +
            "\n\nAdd (max_width, max_height, cap_bytes, variant_kwargs) for each, "
            "or list it in UPLOAD_EXEMPT with a comment explaining why."
        ))

    def test_registry_has_no_entries_for_fields_that_no_longer_exist(self):
        """A stale entry makes the backfill crash on a model it cannot resolve."""
        actual = {key for key, _model, _field in project_file_fields()}
        stale = sorted(set(UPLOAD_LIMITS) - actual)
        self.assertEqual(stale, [], f"UPLOAD_LIMITS mentions dead fields: {stale}")

    def test_every_registered_field_resolves(self):
        """Keys are strings, so a typo would only surface at runtime otherwise."""
        for key in UPLOAD_LIMITS:
            app_label, model_name, field_name = key.split(".")
            model = apps.get_model(app_label, model_name)
            self.assertTrue(
                any(f.name == field_name for f in model._meta.get_fields()),
                f"{key} does not name a real field",
            )

    def test_limits_are_sane(self):
        for key, (width, height, cap, variant) in UPLOAD_LIMITS.items():
            with self.subTest(field=key):
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertGreater(cap, 50 * 1024, "a cap this low would gut every photo")
                self.assertTrue(variant is None or isinstance(variant, dict))

    def test_unregistered_field_raises_instead_of_silently_skipping(self):
        """The runtime half of the guard, for anything the test suite never loads."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            limits_for(apps.get_model("leaderboard", "Event"), "nonexistent")
        self.assertIn("UPLOAD_LIMITS", str(ctx.exception))


class UploadLimitSettingsTests(TestCase):
    """One limit for every format, movable without a deploy."""

    def test_defaults_are_15_mb_and_24_mp(self):
        """Both pinned: they are a memory budget, not a preference.

        24 MP is what imagelab/07_memory.py says fits two gunicorn workers on a
        512 MB instance with headroom. Raising it is a decision to make with a
        measurement in hand.
        """
        self.assertEqual(image_utils.max_upload_bytes(), 15 * 1024 * 1024)
        self.assertEqual(image_utils.max_image_pixels(), 24_000_000)

    def test_settings_override_both_limits(self):
        with self.settings(IMAGE_MAX_UPLOAD_MB=4, IMAGE_MAX_MEGAPIXELS=8):
            self.assertEqual(image_utils.max_upload_bytes(), 4 * 1024 * 1024)
            self.assertEqual(image_utils.max_image_pixels(), 8_000_000)

    def test_error_message_quotes_the_configured_limit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with self.settings(IMAGE_MAX_UPLOAD_MB=1):
            upload = SimpleUploadedFile("big.jpg", b"x" * (2 * 1024 * 1024),
                                        content_type="image/jpeg")
            with self.assertRaises(ValueError) as ctx:
                image_utils.validate_upload(upload)
            self.assertIn("max 1 MB", str(ctx.exception))
