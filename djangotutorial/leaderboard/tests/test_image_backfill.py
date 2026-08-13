"""generate_image_variants: variant backfill + the opt-in --resize downscale."""
import os
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from leaderboard.image_utils import (
    make_webp_variant, needs_resize, resize_image, variant_name,
)
from leaderboard.models import Badge, Event


class _FieldFile:
    """Minimal stand-in for an ImageFieldFile backed by local storage.

    The image utils are storage-abstracted (`.storage` + `.name`), never `.path`,
    so the stub exposes a FileSystemStorage rooted at the file's directory — the
    same shape a real ImageFieldFile presents to those functions.
    """

    def __init__(self, path):
        directory, filename = os.path.split(path)
        self.storage = FileSystemStorage(location=directory)
        self.name = filename

    def __bool__(self):
        return True

    @property
    def url(self):
        return self.storage.url(self.name)


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
        self.assertTrue(needs_resize(_FieldFile(path), 1200, 1200))

    def test_small_and_light_image_is_left_alone(self):
        path = _write_jpeg(self._path("small.jpg"), 600, 400)
        self.assertFalse(needs_resize(_FieldFile(path), 1200, 1200))

    def test_correct_dimensions_but_heavy_still_needs_reencode(self):
        path = _write_jpeg(self._path("heavy.jpg"), 1100, 1100, noisy=True)
        self.assertGreater(os.path.getsize(path), 500 * 1024)
        self.assertTrue(needs_resize(_FieldFile(path), 1200, 1200))

    def test_missing_file_is_not_a_candidate(self):
        self.assertFalse(needs_resize(_FieldFile(self._path("nope.jpg")), 1200, 1200))

    def test_non_image_is_not_a_candidate(self):
        path = self._path("junk.jpg")
        with open(path, "w") as fh:
            fh.write("definitely not a jpeg")
        self.assertFalse(needs_resize(_FieldFile(path), 1200, 1200))


class FormatPreservationTests(TestCase):
    """resize_image must never rewrite a file as a different format.

    The original implementation force-saved anything that wasn't .jpg/.png as
    JPEG *to the same path*, so a .gif or .webp logo ended up as JPEG bytes
    under its old extension, with transparency (and any animation) gone.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def _resize(self, path, **kwargs):
        resize_image(_FieldFile(path), max_width=512, max_height=512, **kwargs)

    def test_svg_is_left_byte_for_byte(self):
        path = self._path("logo.svg")
        with open(path, "w") as fh:
            fh.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="9000"/></svg>')
        before = open(path, "rb").read()
        self._resize(path)
        self.assertEqual(open(path, "rb").read(), before)

    def test_svg_gets_no_webp_variant(self):
        path = self._path("logo.svg")
        with open(path, "w") as fh:
            fh.write("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
        make_webp_variant(_FieldFile(path))
        self.assertFalse(os.path.exists(variant_name(path)))

    def test_gif_is_not_rewritten_as_jpeg(self):
        path = self._path("logo.gif")
        Image.new("P", (2000, 2000)).save(path, "GIF")
        self._resize(path)
        with Image.open(path) as img:
            self.assertEqual(img.format, "GIF")

    def test_webp_stays_webp(self):
        path = self._path("logo.webp")
        Image.new("RGBA", (2000, 2000), (255, 0, 0, 128)).save(path, "WEBP")
        self._resize(path)
        with Image.open(path) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertLessEqual(img.width, 512)

    def test_png_keeps_its_alpha_channel(self):
        """Event logos are transparent PNGs — flattening them is visible damage."""
        path = self._path("logo.png")
        Image.new("RGBA", (2000, 2000), (255, 0, 0, 0)).save(path, "PNG")
        self._resize(path)
        with Image.open(path) as img:
            self.assertEqual(img.format, "PNG")
            self.assertIn("A", img.mode)
            self.assertLessEqual(img.width, 512)

    def test_animated_webp_is_not_flattened(self):
        path = self._path("anim.webp")
        frames = [Image.new("RGB", (900, 900), c) for c in ("red", "blue", "green")]
        frames[0].save(path, "WEBP", save_all=True, append_images=frames[1:], duration=80)
        self._resize(path)
        with Image.open(path) as img:
            self.assertGreater(getattr(img, "n_frames", 1), 1)

    def test_unknown_extension_is_ignored(self):
        path = self._path("thing.bmp")
        Image.new("RGB", (2000, 2000)).save(path, "BMP")
        before = os.path.getsize(path)
        self._resize(path)
        self.assertEqual(os.path.getsize(path), before)


class BadgeArtworkTests(TestCase):
    """Badge.image is the old event logo: never resized or variant-ed before, in
    save() or the backfill. Same guarantees, new home."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(MEDIA_ROOT=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def _badge_with_image(self, name="badges/big.png", size=(2000, 2000)):
        badge = Badge.objects.create(name="S logem")
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.new("RGBA", size, (255, 0, 0, 128)).save(path, "PNG")
        Badge.objects.filter(pk=badge.pk).update(image=name)
        return Badge.objects.get(pk=badge.pk), path

    def test_save_downscales_new_artwork(self):
        badge, path = self._badge_with_image()
        badge.save()
        with Image.open(path) as img:
            self.assertLessEqual(img.width, 512)
            self.assertIn("A", img.mode)

    def test_backfill_downscales_legacy_artwork(self):
        _, path = self._badge_with_image()
        before = os.path.getsize(path)
        call_command("generate_image_variants", resize=True, stdout=StringIO())
        with Image.open(path) as img:
            self.assertLessEqual(img.width, 512)
        self.assertLess(os.path.getsize(path), before)

    def test_artwork_gets_no_webp_sibling(self):
        """At 512px a variant would save nothing and only add a file."""
        _, path = self._badge_with_image()
        call_command("generate_image_variants", resize=True, stdout=StringIO())
        self.assertFalse(os.path.exists(variant_name(path)))

    def test_svg_artwork_survives_the_backfill(self):
        badge = Badge.objects.create(name="SVG logo")
        path = os.path.join(self.tmp.name, "badges/logo.svg")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>")
        Badge.objects.filter(pk=badge.pk).update(image="badges/logo.svg")
        before = open(path, "rb").read()
        call_command("generate_image_variants", resize=True, stdout=StringIO())
        self.assertEqual(open(path, "rb").read(), before)


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
