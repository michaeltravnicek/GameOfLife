"""Uploads are stored as WebP: conversion, the size cap, and the backfill command.

Until 2026-08 every upload kept its incoming format, which meant a PNG screenshot
stayed a multi-megabyte PNG forever -- lossless, so there was no quality knob to
turn. Everything is now re-encoded as WebP under a per-model byte cap, which also
renames the stored file and therefore the key held in the database row. These
tests pin that rename down, because it is the part that can lose an image.
"""
import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from leaderboard import image_utils
from leaderboard.image_utils import (
    CAP_ARTWORK, CAP_EVENT_IMAGE, WEBP_QUALITY, WEBP_QUALITY_FLOOR,
    _encode_under_cap, make_webp_variant, needs_processing, process_upload,
    variant_name, webp_name,
)
from leaderboard.models import Badge, Event, ImageToEvent, UserPhoto


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


class _TmpDirTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def _sibling(self, path, name):
        return os.path.join(os.path.dirname(path), name)


class NeedsProcessingTests(_TmpDirTestCase):
    """The predicate the backfill dry-run reports from."""

    def test_oversized_dimensions_qualify(self):
        path = _write_jpeg(self._path("big.jpg"), 3000, 2000)
        self.assertTrue(needs_processing(_FieldFile(path), 1200, 1200, CAP_EVENT_IMAGE))

    def test_small_jpeg_still_qualifies_because_it_is_not_webp(self):
        """Format conversion alone is reason enough — this is what changed."""
        path = _write_jpeg(self._path("small.jpg"), 600, 400)
        self.assertTrue(needs_processing(_FieldFile(path), 1200, 1200, CAP_EVENT_IMAGE))

    def test_webp_within_limits_is_left_alone(self):
        path = self._path("done.webp")
        Image.new("RGB", (600, 400), (10, 20, 30)).save(path, "WEBP", quality=WEBP_QUALITY)
        self.assertFalse(needs_processing(_FieldFile(path), 1200, 1200, CAP_EVENT_IMAGE))

    def test_webp_over_the_cap_qualifies(self):
        path = self._path("heavy.webp")
        Image.effect_noise((1200, 1200), 96).convert("RGB").save(
            path, "WEBP", quality=95, method=0)
        self.assertGreater(os.path.getsize(path), 200 * 1024)
        self.assertTrue(needs_processing(_FieldFile(path), 1200, 1200, 200 * 1024))

    def test_webp_over_the_dimensions_qualifies(self):
        path = self._path("wide.webp")
        Image.new("RGB", (2000, 500)).save(path, "WEBP")
        self.assertTrue(needs_processing(_FieldFile(path), 1200, 1200, CAP_EVENT_IMAGE))

    def test_missing_file_is_not_a_candidate(self):
        self.assertFalse(
            needs_processing(_FieldFile(self._path("nope.jpg")), 1200, 1200, CAP_EVENT_IMAGE))

    def test_non_image_is_not_a_candidate(self):
        path = self._path("junk.jpg")
        with open(path, "w") as fh:
            fh.write("definitely not a jpeg")
        self.assertFalse(needs_processing(_FieldFile(path), 1200, 1200, CAP_EVENT_IMAGE))

    def test_svg_is_not_a_candidate(self):
        path = self._path("logo.svg")
        with open(path, "w") as fh:
            fh.write("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
        self.assertFalse(needs_processing(_FieldFile(path), 512, 512, CAP_ARTWORK))


class ConversionTests(_TmpDirTestCase):
    """process_upload: what comes out, and under which key."""

    def _convert(self, path, max_side=512, cap=CAP_ARTWORK):
        field = _FieldFile(path)
        return process_upload(field, max_side, max_side, cap)

    def test_jpeg_becomes_webp_under_a_new_key(self):
        path = _write_jpeg(self._path("photo.jpg"), 2000, 1500)
        new_name = self._convert(path)
        self.assertEqual(new_name, "photo.webp")
        with Image.open(self._sibling(path, new_name)) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertLessEqual(img.width, 512)

    def test_source_file_is_removed_after_conversion(self):
        """Leaving it behind would double the storage bill for every image."""
        path = _write_jpeg(self._path("photo.jpg"), 900, 900)
        self._convert(path)
        self.assertFalse(os.path.exists(path))

    def test_real_transparency_survives(self):
        """Event artwork is transparent PNG — flattening it is visible damage."""
        path = self._path("logo.png")
        img = Image.new("RGBA", (900, 900), (255, 0, 0, 0))
        img.putpixel((0, 0), (0, 255, 0, 255))
        img.save(path, "PNG")
        new_name = self._convert(path)
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertEqual(out.format, "WEBP")
            self.assertIn("A", out.mode)

    def test_fully_opaque_alpha_channel_is_dropped(self):
        """An all-255 alpha channel is a quarter of the data carrying nothing."""
        path = self._path("opaque.png")
        Image.new("RGBA", (600, 600), (12, 34, 56, 255)).save(path, "PNG")
        new_name = self._convert(path)
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertNotIn("A", out.mode)

    def test_animated_gif_becomes_animated_webp(self):
        """GIF used to bypass processing entirely and could sit at the full 15 MB."""
        path = self._path("anim.gif")
        # Frames must genuinely differ: the GIF encoder collapses identical ones,
        # and the test would then be asserting on a single-frame file.
        frames = [Image.new("RGB", (800, 800), c).convert("P")
                  for c in ("red", "blue", "green")]
        frames[0].save(path, "GIF", save_all=True, append_images=frames[1:], duration=80)
        with Image.open(path) as probe:
            self.assertGreater(probe.n_frames, 1, "fixture is not animated")
        new_name = self._convert(path)
        self.assertEqual(new_name, "anim.webp")
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertEqual(out.format, "WEBP")
            self.assertGreater(getattr(out, "n_frames", 1), 1)

    def test_svg_is_left_byte_for_byte(self):
        path = self._path("logo.svg")
        with open(path, "w") as fh:
            fh.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="9000"/></svg>')
        before = open(path, "rb").read()
        self.assertIsNone(self._convert(path))
        self.assertEqual(open(path, "rb").read(), before)

    def test_svg_gets_no_webp_variant(self):
        path = self._path("logo.svg")
        with open(path, "w") as fh:
            fh.write("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
        make_webp_variant(_FieldFile(path))
        self.assertFalse(os.path.exists(variant_name(path)))

    def test_corrupt_file_is_left_alone(self):
        path = self._path("junk.jpg")
        with open(path, "w") as fh:
            fh.write("not an image")
        self.assertIsNone(self._convert(path))
        self.assertTrue(os.path.exists(path))

    def test_second_conversion_is_a_no_op(self):
        """Every model save() calls this, so re-encoding would decay the image."""
        path = _write_jpeg(self._path("photo.jpg"), 900, 900)
        new_name = self._convert(path)
        converted = self._sibling(path, new_name)
        settled = open(converted, "rb").read()

        again = process_upload(_FieldFile(converted), 512, 512, CAP_ARTWORK)
        self.assertIsNone(again)
        self.assertEqual(open(converted, "rb").read(), settled)

    def test_colliding_names_do_not_overwrite_each_other(self):
        """'logo.png' and 'logo.jpg' both want 'logo.webp' — one must give way."""
        png = self._path("logo.png")
        Image.new("RGB", (400, 400), (255, 0, 0)).save(png, "PNG")
        jpg = _write_jpeg(self._path("logo.jpg"), 400, 400)

        first = self._convert(png)
        second = self._convert(jpg)
        self.assertEqual(first, "logo.webp")
        self.assertNotEqual(second, first)
        self.assertTrue(os.path.exists(self._sibling(png, first)))
        self.assertTrue(os.path.exists(self._sibling(jpg, second)))


class AnimationBudgetTests(_TmpDirTestCase):
    """Animations hold every frame in RAM at once, so they need their own limits.

    A still costs one bitmap; an animation costs frames x width x height, and the
    15 MB upload limit does not bound that -- a well-compressed GIF can carry
    hundreds of frames. Both guards shrink the animation rather than rejecting
    it, so the upload still works. See imagelab/07_memory.py.
    """

    def _gif(self, frames=8, side=200):
        path = self._path("anim.gif")
        imgs = [Image.new("RGB", (side, side), (i * 30 % 256, 90, 200)).convert("P")
                for i in range(frames)]
        imgs[0].save(path, "GIF", save_all=True, append_images=imgs[1:], duration=60)
        return path

    def test_frame_count_is_capped(self):
        path = self._gif(frames=8)
        with mock.patch.object(image_utils, "MAX_ANIMATION_FRAMES", 3):
            new_name = process_upload(_FieldFile(path), 512, 512, CAP_ARTWORK)
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertEqual(out.n_frames, 3)

    def test_frames_shrink_to_fit_the_pixel_budget(self):
        path = self._gif(frames=8, side=200)
        # Budget for 8 frames of 50x50 — every frame must come down to fit.
        with mock.patch.object(image_utils, "MAX_ANIMATION_PIXELS", 8 * 50 * 50):
            new_name = process_upload(_FieldFile(path), 512, 512, CAP_ARTWORK)
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertLessEqual(out.width, 50)
            self.assertGreater(out.n_frames, 1, "still has to be an animation")

    def test_animation_inside_the_budget_is_untouched(self):
        path = self._gif(frames=4, side=200)
        new_name = process_upload(_FieldFile(path), 512, 512, CAP_ARTWORK)
        with Image.open(self._sibling(path, new_name)) as out:
            self.assertEqual(out.n_frames, 4)
            self.assertEqual(out.width, 200)


class SizeCapTests(_TmpDirTestCase):
    """The cap is a guard rail; these are the pathological inputs that reach it."""

    def test_heavy_image_is_forced_under_the_cap(self):
        path = self._path("noise.jpg")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.effect_noise((1200, 1200), 96).convert("RGB").save(path, "JPEG", quality=98)
        cap = 60 * 1024
        new_name = process_upload(_FieldFile(path), 1200, 1200, cap)
        self.assertLessEqual(os.path.getsize(self._sibling(path, new_name)), cap)

    def test_cap_shrinks_dimensions_once_quality_bottoms_out(self):
        path = self._path("noise.jpg")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.effect_noise((1200, 1200), 96).convert("RGB").save(path, "JPEG", quality=98)
        new_name = process_upload(_FieldFile(path), 1200, 1200, 40 * 1024)
        with Image.open(self._sibling(path, new_name)) as img:
            self.assertLess(img.width, 1200)

    def test_ordinary_photo_never_reaches_the_floor(self):
        """If routine uploads hit the ladder, the caps are set wrong."""
        path = _write_jpeg(self._path("normal.jpg"), 1600, 1200)
        new_name = process_upload(_FieldFile(path), 1600, 1600, CAP_EVENT_IMAGE)
        self.assertLess(os.path.getsize(self._sibling(path, new_name)), CAP_EVENT_IMAGE)

    def test_floor_above_start_quality_does_not_return_nothing(self):
        """Lowering WEBP_QUALITY without touching the floor must not crash uploads.

        The descending range is empty when the floor sits above the start, and an
        unclamped version returned None here — which surfaces as a failed upload,
        not as a bad-looking image.
        """
        img = Image.new("RGB", (200, 200), (5, 5, 5))
        payload = _encode_under_cap([img], 10, quality=WEBP_QUALITY_FLOOR - 10,
                                    floor=WEBP_QUALITY_FLOOR)
        self.assertTrue(payload)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModelSaveTests(TestCase):
    """save() must persist the new key — otherwise the row points at a dead file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(MEDIA_ROOT=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def _attach(self, model, pk, field, name, factory):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        factory(path)
        model.objects.filter(pk=pk).update(**{field: name})
        return path

    def _event(self):
        return Event.objects.create(
            sheet_id="s1", sheet_list_id="x", name="Akce", place="Brno",
            points=10, date=timezone.now() + timedelta(days=1),
        )

    def test_event_save_rewrites_the_stored_key(self):
        event = self._event()
        self._attach(Event, event.pk, "image", "event_images/e.jpg",
                     lambda p: _write_jpeg(p, 2000, 1500))
        event = Event.objects.get(pk=event.pk)
        event.save()

        event.refresh_from_db()
        self.assertEqual(event.image.name, "event_images/e.webp")
        self.assertTrue(event.image.storage.exists(event.image.name))

    def test_event_variant_sits_next_to_the_new_key(self):
        """Generated before the rename, the variant would be orphaned."""
        event = self._event()
        self._attach(Event, event.pk, "image", "event_images/e.jpg",
                     lambda p: _write_jpeg(p, 2000, 1500))
        event = Event.objects.get(pk=event.pk)
        event.save()

        event.refresh_from_db()
        self.assertTrue(event.image.storage.exists(variant_name(event.image.name)))
        self.assertEqual(variant_name(event.image.name), "event_images/e.mobile.webp")

    def test_badge_save_rewrites_the_stored_key(self):
        badge = Badge.objects.create(name="Odznak")
        self._attach(Badge, badge.pk, "image", "badges/b.png",
                     lambda p: Image.new("RGBA", (2000, 2000), (255, 0, 0, 128)).save(p, "PNG"))
        badge = Badge.objects.get(pk=badge.pk)
        badge.save()

        badge.refresh_from_db()
        self.assertEqual(badge.image.name, "badges/b.webp")

    def test_user_photo_save_lands_under_the_cap(self):
        user = self._user()
        photo = UserPhoto.objects.create(auth_user=user, image="user_photos/p.jpg")
        self._attach(UserPhoto, photo.pk, "image", "user_photos/p.jpg",
                     lambda p: _write_jpeg(p, 2400, 2400, noisy=True))
        photo = UserPhoto.objects.get(pk=photo.pk)
        photo.save()

        photo.refresh_from_db()
        self.assertTrue(photo.image.name.endswith(".webp"))
        self.assertLessEqual(photo.image.storage.size(photo.image.name), 700 * 1024)

    def test_saving_twice_does_not_re_encode(self):
        event = self._event()
        self._attach(Event, event.pk, "image", "event_images/e.jpg",
                     lambda p: _write_jpeg(p, 2000, 1500))
        event = Event.objects.get(pk=event.pk)
        event.save()
        event.refresh_from_db()
        first = event.image.storage.open(event.image.name, "rb").read()

        event.save()
        event.refresh_from_db()
        self.assertEqual(event.image.name, "event_images/e.webp")
        self.assertEqual(event.image.storage.open(event.image.name, "rb").read(), first)

    def _user(self):
        from django.contrib.auth.models import User
        return User.objects.create_user(username="hrac", password="x")

    def test_image_to_event_save_rewrites_the_stored_key(self):
        event = self._event()
        rel = ImageToEvent.objects.create(event=event, image="event_images/i.jpg")
        self._attach(ImageToEvent, rel.pk, "image", "event_images/i.jpg",
                     lambda p: _write_jpeg(p, 1800, 1800))
        rel = ImageToEvent.objects.get(pk=rel.pk)
        rel.save()

        rel.refresh_from_db()
        self.assertEqual(rel.image.name, "event_images/i.webp")


class BadgeArtworkTests(TestCase):
    """Badge.image is the old event logo: no .mobile.webp sibling, SVG untouched."""

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

    def test_backfill_converts_legacy_artwork(self):
        badge, path = self._badge_with_image()
        before = os.path.getsize(path)
        call_command("generate_image_variants", resize=True, stdout=StringIO())

        badge.refresh_from_db()
        self.assertEqual(badge.image.name, "badges/big.webp")
        converted = os.path.join(self.tmp.name, badge.image.name)
        with Image.open(converted) as img:
            self.assertLessEqual(img.width, 512)
        self.assertLess(os.path.getsize(converted), before)

    def test_artwork_gets_no_webp_sibling(self):
        """At 512px a variant would save nothing and only add a file."""
        badge, _ = self._badge_with_image()
        call_command("generate_image_variants", resize=True, stdout=StringIO())
        badge.refresh_from_db()
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, variant_name(badge.image.name))))

    def test_svg_artwork_survives_the_backfill(self):
        badge = Badge.objects.create(name="SVG logo")
        path = os.path.join(self.tmp.name, "badges/logo.svg")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>")
        Badge.objects.filter(pk=badge.pk).update(image="badges/logo.svg")
        before = open(path, "rb").read()

        call_command("generate_image_variants", resize=True, stdout=StringIO())

        badge.refresh_from_db()
        self.assertEqual(badge.image.name, "badges/logo.svg")
        self.assertEqual(open(path, "rb").read(), before)


class BackfillCommandTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(MEDIA_ROOT=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def _legacy_event(self, width=3750, height=5000, name="event_images/legacy.jpg"):
        """An event whose file predates the conversion in save().

        The image is attached with .update() so Event.save() -- which would
        convert it immediately -- never runs on it. That's the real situation
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

    def test_resize_converts_and_repoints_the_row(self):
        event, path = self._legacy_event()
        before = os.path.getsize(path)
        self._run(resize=True)

        event.refresh_from_db()
        self.assertEqual(event.image.name, "event_images/legacy.webp")
        converted = os.path.join(self.tmp.name, event.image.name)
        with Image.open(converted) as img:
            self.assertLessEqual(img.width, 1200)
            self.assertLessEqual(img.height, 1200)
        self.assertLess(os.path.getsize(converted), before)
        self.assertFalse(os.path.exists(path))

    def test_resize_reports_bytes_freed(self):
        self._legacy_event()
        output = self._run(resize=True)
        self.assertIn("Converted 1 originals", output)
        self.assertIn("freed", output)

    def test_dry_run_writes_nothing(self):
        event, path = self._legacy_event()
        before = os.path.getsize(path)
        output = self._run(resize=True, dry_run=True)

        event.refresh_from_db()
        self.assertEqual(event.image.name, "event_images/legacy.jpg")
        self.assertEqual(os.path.getsize(path), before)
        self.assertFalse(os.path.exists(variant_name(path)))
        self.assertIn("would convert", output)

    def test_second_resize_run_is_a_no_op(self):
        event, _ = self._legacy_event()
        self._run(resize=True)
        event.refresh_from_db()
        converted = os.path.join(self.tmp.name, event.image.name)
        settled = os.path.getsize(converted)

        output = self._run(resize=True)
        self.assertEqual(os.path.getsize(converted), settled)
        self.assertIn("Converted 0 originals", output)

    def test_missing_file_is_counted_not_crashed(self):
        event = Event.objects.create(
            sheet_id="bk2", sheet_list_id="x", name="Ghost",
            place="Brno", points=10, date=timezone.now() + timedelta(days=1),
        )
        Event.objects.filter(pk=event.pk).update(image="event_images/gone.jpg")
        self.assertIn("missing files 1", self._run(resize=True))
