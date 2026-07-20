"""EventWriteSerializer logo handling — SVG must be accepted (regression guard).

Before FileField, logo was the auto ImageField, which Pillow-verifies and so
rejected SVG. Logos are commonly SVG, so this must keep working.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from leaderboard.api.serializers import EventWriteSerializer
from leaderboard.models import Event

_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
# 1x1 transparent PNG.
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _svg(name="logo.svg"):
    return SimpleUploadedFile(name, _SVG, content_type="image/svg+xml")


class EventLogoUploadTests(TestCase):
    def _base_data(self):
        return {"name": "Akce", "place": "Brno", "points": "10",
                "date": (timezone.now()).isoformat()}

    def test_svg_logo_accepted_on_create(self):
        s = EventWriteSerializer(data={**self._base_data(), "logo": _svg()})
        self.assertTrue(s.is_valid(), s.errors)

    def test_raster_logo_still_accepted(self):
        png = SimpleUploadedFile("logo.png", _PNG, content_type="image/png")
        s = EventWriteSerializer(data={**self._base_data(), "logo": png})
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_image_logo_rejected(self):
        bad = SimpleUploadedFile("logo.txt", b"nope", content_type="text/plain")
        s = EventWriteSerializer(data={**self._base_data(), "logo": bad})
        self.assertFalse(s.is_valid())
        self.assertIn("logo", s.errors)

    def test_svg_logo_saves_and_serves_url(self):
        # End-to-end through save(): the SVG logo must persist and expose a URL.
        s = EventWriteSerializer(data={**self._base_data(), "logo": _svg()})
        self.assertTrue(s.is_valid(), s.errors)
        event = s.save()
        event.refresh_from_db()
        self.assertTrue(event.logo)
        self.assertTrue(event.logo.url.endswith(".svg"))

    def test_svg_poster_image_still_rejected(self):
        # The poster `image` is resized by Pillow, so SVG there must NOT pass.
        s = EventWriteSerializer(data={**self._base_data(), "image": _svg("poster.svg")})
        self.assertFalse(s.is_valid())
        self.assertIn("image", s.errors)
