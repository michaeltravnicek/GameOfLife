"""Logo handling — SVG must be accepted (regression guard), and events must not
be able to upload artwork of their own any more.

The logo used to be Event.logo, an ImageField that Pillow-verifies and so
rejected SVG; it became a FileField for that reason. The artwork has since moved
to Badge (one row per image instead of one file per event), so the same SVG
guard now belongs to BadgeWriteSerializer.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from leaderboard.api.serializers import BadgeWriteSerializer, EventWriteSerializer
from leaderboard.models import Badge, Event

_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
# 1x1 transparent PNG.
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _svg(name="logo.svg"):
    return SimpleUploadedFile(name, _SVG, content_type="image/svg+xml")


class BadgeArtworkUploadTests(TestCase):
    def test_svg_artwork_accepted(self):
        s = BadgeWriteSerializer(data={"name": "Karaoke", "image": _svg()})
        self.assertTrue(s.is_valid(), s.errors)

    def test_raster_artwork_still_accepted(self):
        png = SimpleUploadedFile("logo.png", _PNG, content_type="image/png")
        s = BadgeWriteSerializer(data={"name": "Karaoke", "image": png})
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_image_artwork_rejected(self):
        bad = SimpleUploadedFile("logo.txt", b"nope", content_type="text/plain")
        s = BadgeWriteSerializer(data={"name": "Karaoke", "image": bad})
        self.assertFalse(s.is_valid())
        self.assertIn("image", s.errors)

    def test_svg_artwork_saves_and_serves_url(self):
        # End-to-end through save(): the SVG must persist and expose a URL.
        s = BadgeWriteSerializer(data={"name": "Karaoke", "image": _svg()})
        self.assertTrue(s.is_valid(), s.errors)
        badge = s.save()
        badge.refresh_from_db()
        self.assertTrue(badge.image)
        self.assertTrue(badge.image.url.endswith(".svg"))


class EventArtworkTests(TestCase):
    def _base_data(self):
        return {"name": "Akce", "place": "Brno", "points": "10",
                "date": (timezone.now()).isoformat()}

    def test_event_takes_a_badge_not_a_logo_file(self):
        badge = Badge.objects.create(name="Karaoke")
        s = EventWriteSerializer(data={**self._base_data(), "badge": badge.id})
        self.assertTrue(s.is_valid(), s.errors)
        event = s.save()
        self.assertEqual(event.badge_id, badge.id)

    def test_logo_upload_is_ignored(self):
        """An old client still POSTing a logo file must not resurrect per-event
        artwork — the field is gone, so DRF drops it."""
        s = EventWriteSerializer(data={**self._base_data(), "logo": _svg()})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("logo", s.validated_data)
        event = s.save()
        self.assertFalse(hasattr(event, "logo"))

    def test_empty_badge_clears_the_link(self):
        """A <select> with nothing chosen posts "" in multipart form data."""
        badge = Badge.objects.create(name="Karaoke")
        event = Event.objects.create(
            name="Akce", place="Brno", points=10,
            date=timezone.now() + timedelta(days=1), badge=badge,
        )
        s = EventWriteSerializer(event, data={"badge": ""}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.save().badge_id)

    def test_svg_poster_image_still_rejected(self):
        # The poster `image` is resized by Pillow, so SVG there must NOT pass.
        s = EventWriteSerializer(data={**self._base_data(), "image": _svg("poster.svg")})
        self.assertFalse(s.is_valid())
        self.assertIn("image", s.errors)
