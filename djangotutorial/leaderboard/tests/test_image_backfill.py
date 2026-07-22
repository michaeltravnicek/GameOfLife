"""generate_image_variants: variant backfill + the opt-in --resize downscale."""
import os
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from leaderboard.image_utils import needs_resize, variant_name
from leaderboard.models import Event


def _write_jpeg(path, width, height, noisy=False):
    """Write a JPEG of the given dimensions; `noisy` makes it heavy on disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if noisy:
        img = Image.effect_noise((width, height), 96).convert("RGB")
    else:
        img = Image.new("RGB", (width, height), (200, 80, 90))
    img.save(path, "JPEG", quality=95)
    return path


class NeedsResizeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_oversized_dimensions_need_resize(self):
        path = _write_jpeg(self._path("big.jpg"), 3000, 2000)
        self.assertTrue(needs_resize(path, 1200, 1200))

    def test_small_and_light_image_is_left_alone(self):
        path = _write_jpeg(self._path("small.jpg"), 600, 400)
        self.assertFalse(needs_resize(path, 1200, 1200))

    def test_correct_dimensions_but_heavy_still_needs_reencode(self):
        path = _write_jpeg(self._path("heavy.jpg"), 1100, 1100, noisy=True)
        self.assertGreater(os.path.getsize(path), 500 * 1024)
        self.assertTrue(needs_resize(path, 1200, 1200))

    def test_missing_file_is_not_a_candidate(self):
        self.assertFalse(needs_resize(self._path("nope.jpg"), 1200, 1200))

    def test_non_image_is_not_a_candidate(self):
        path = self._path("junk.jpg")
        with open(path, "w") as fh:
            fh.write("definitely not a jpeg")
        self.assertFalse(needs_resize(path, 1200, 1200))


class BackfillCommandTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(MEDIA_ROOT=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def _legacy_event(self, width=3750, height=5000, name="event_images/legacy.jpg"):
        """An event whose file predates resize_image().

        The image is attached with .update() so Event.save() -- which would
        resize it immediately -- never runs on it. That's the real situation
        this command exists for.
        """
        event = Event.objects.create(
            sheet_id="bk1", sheet_list_id="x", name="Legacy",
            place="Brno", points=10, date=timezone.now() + timedelta(days=1),
        )
        path = _write_jpeg(os.path.join(self.tmp.name, name), width, height)
        Event.objects.filter(pk=event.pk).update(image=name)
        return Event.objects.get(pk=event.pk), path

    def _run(self, **kwargs):
        out = StringIO()
        call_command("generate_image_variants", stdout=out, **kwargs)
        return out.getvalue()

    def test_default_run_does_not_touch_originals(self):
        """build.sh runs this on every deploy — it must stay non-destructive."""
        _, path = self._legacy_event()
        before = os.path.getsize(path)
        self._run()
        self.assertEqual(os.path.getsize(path), before)
        with Image.open(path) as img:
            self.assertEqual(img.width, 3750)

    def test_default_run_still_generates_the_variant(self):
        _, path = self._legacy_event()
        self._run()
        self.assertTrue(os.path.exists(variant_name(path)))

    def test_resize_downscales_the_original(self):
        _, path = self._legacy_event()
        before = os.path.getsize(path)
        self._run(resize=True)
        with Image.open(path) as img:
            self.assertLessEqual(img.width, 1200)
            self.assertLessEqual(img.height, 1200)
        self.assertLess(os.path.getsize(path), before)

    def test_resize_reports_bytes_freed(self):
        self._legacy_event()
        output = self._run(resize=True)
        self.assertIn("Resized 1 originals", output)
        self.assertIn("freed", output)

    def test_dry_run_writes_nothing(self):
        _, path = self._legacy_event()
        before = os.path.getsize(path)
        output = self._run(resize=True, dry_run=True)
        self.assertEqual(os.path.getsize(path), before)
        self.assertFalse(os.path.exists(variant_name(path)))
        self.assertIn("would resize", output)

    def test_resize_regenerates_a_stale_variant(self):
        """A variant built from the pre-resize original must not survive."""
        _, path = self._legacy_event()
        self._run()  # variant from the 3750px original
        stale_mtime = os.path.getmtime(variant_name(path))
        os.utime(variant_name(path), (stale_mtime - 60, stale_mtime - 60))
        self._run(resize=True)
        self.assertGreater(os.path.getmtime(variant_name(path)), stale_mtime - 60)

    def test_second_resize_run_is_a_no_op(self):
        _, path = self._legacy_event()
        self._run(resize=True)
        settled = os.path.getsize(path)
        output = self._run(resize=True)
        self.assertEqual(os.path.getsize(path), settled)
        self.assertIn("Resized 0 originals", output)

    def test_already_small_image_is_not_resized(self):
        _, path = self._legacy_event(width=800, height=600, name="event_images/ok.jpg")
        before = os.path.getsize(path)
        self._run(resize=True)
        self.assertEqual(os.path.getsize(path), before)

    def test_missing_file_is_counted_not_crashed(self):
        event = Event.objects.create(
            sheet_id="bk2", sheet_list_id="x", name="Ghost",
            place="Brno", points=10, date=timezone.now() + timedelta(days=1),
        )
        Event.objects.filter(pk=event.pk).update(image="event_images/gone.jpg")
        self.assertIn("missing files 1", self._run(resize=True))
