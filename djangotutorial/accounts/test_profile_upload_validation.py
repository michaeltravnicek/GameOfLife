"""The avatar sent with the profile form goes through validate_upload.

The media origin serves a file with the content type its extension implies, so
an upload kept under the client's own name (`evil.html`) is stored XSS. Two
layers stop it: validate_upload at the API, and the image pipeline refusing to
keep a file whose key is not an image type, whatever path reached save().
"""
import io
import os
import shutil
import tempfile

from django.contrib.auth.models import User as AuthUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Profile
from leaderboard.models import Badge
from leaderboard.tests.helpers import make_image_upload

_HTML = b"<html><body><script>alert(document.cookie)</script></body></html>"
_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"


def _png_bytes(size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format="PNG")
    return buf.getvalue()


class _MediaRootTestCase(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def _stored_files(self):
        found = []
        for root, _dirs, files in os.walk(self.media):
            found += [os.path.relpath(os.path.join(root, f), self.media) for f in files]
        return found


class ProfileUpdatePhotoValidationTests(_MediaRootTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.url = reverse("api-profile-update")
        self.user = AuthUser.objects.create_user(username="pat", password="x", first_name="Pat")
        Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def _post(self, upload, **extra):
        return self.client.post(self.url, {"photo": upload, **extra}, format="multipart")

    def _assert_rejected(self, resp):
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
        self.assertFalse(Profile.objects.get(user=self.user).photo)
        self.assertEqual(self._stored_files(), [])

    def test_html_is_rejected_and_nothing_stored(self):
        self._assert_rejected(self._post(
            SimpleUploadedFile("evil.html", _HTML, content_type="text/html")))

    def test_html_claiming_an_image_type_is_rejected(self):
        self._assert_rejected(self._post(
            SimpleUploadedFile("evil.png", _HTML, content_type="image/png")))

    def test_svg_is_rejected(self):
        self._assert_rejected(self._post(
            SimpleUploadedFile("evil.svg", _SVG, content_type="image/svg+xml")))

    def test_rejected_photo_leaves_the_other_fields_unwritten(self):
        resp = self._post(SimpleUploadedFile("evil.html", _HTML, content_type="text/html"),
                          first_name="Hacked", bio="nope")
        self._assert_rejected(resp)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Pat")
        self.assertEqual(Profile.objects.get(user=self.user).bio, "")

    def test_oversized_file_is_rejected(self):
        with self.settings(IMAGE_MAX_UPLOAD_MB=1):
            big = SimpleUploadedFile("big.png", _png_bytes() + b"\0" * (1024 * 1024),
                                     content_type="image/png")
            self._assert_rejected(self._post(big))

    def test_small_png_is_stored(self):
        resp = self._post(make_image_upload("a.png"))
        self.assertEqual(resp.status_code, 200)
        photo = Profile.objects.get(user=self.user).photo
        self.assertTrue(photo)
        self.assertEqual(os.path.splitext(photo.name)[1], ".png")
        self.assertTrue(photo.storage.exists(photo.name))

    def test_small_jpeg_is_stored(self):
        resp = self._post(make_image_upload("a.jpg", image_format="JPEG",
                                            content_type="image/jpeg"))
        self.assertEqual(resp.status_code, 200)
        photo = Profile.objects.get(user=self.user).photo
        self.assertEqual(os.path.splitext(photo.name)[1], ".jpg")
        self.assertTrue(photo.storage.exists(photo.name))

    def test_real_image_under_a_html_name_is_stored_under_its_format(self):
        resp = self._post(SimpleUploadedFile("evil.html", _png_bytes(), content_type="image/png"))
        self.assertEqual(resp.status_code, 200)
        photo = Profile.objects.get(user=self.user).photo
        self.assertEqual(os.path.splitext(photo.name)[1], ".webp")
        self.assertFalse(any(f.endswith(".html") for f in self._stored_files()))


class PipelineRefusesUnservableKeysTests(_MediaRootTestCase):
    """Saving straight through the model, past validate_upload."""

    def setUp(self):
        super().setUp()
        self.user = AuthUser.objects.create_user(username="pat", password="x")
        self.profile = Profile.objects.create(user=self.user)

    def test_html_is_deleted_and_the_save_refused(self):
        self.profile.photo = SimpleUploadedFile("evil.html", _HTML, content_type="text/html")
        with self.assertRaises(ValidationError):
            self.profile.save()
        self.assertEqual(self._stored_files(), [])
        self.assertFalse(Profile.objects.get(pk=self.profile.pk).photo)

    def test_undecodable_image_header_under_a_html_name_is_refused(self):
        truncated = _png_bytes(size=(64, 64))[:60] + _HTML
        self.profile.photo = SimpleUploadedFile("poly.html", truncated, content_type="image/png")
        with self.assertRaises(ValidationError):
            self.profile.save()
        self.assertEqual(self._stored_files(), [])

    def test_svg_is_refused_on_a_raster_field(self):
        self.profile.photo = SimpleUploadedFile("x.svg", _SVG, content_type="image/svg+xml")
        with self.assertRaises(ValidationError):
            self.profile.save()
        self.assertEqual(self._stored_files(), [])

    def test_svg_badge_artwork_is_kept(self):
        badge = Badge(name="Vector")
        badge.image = SimpleUploadedFile("logo.svg", _SVG, content_type="image/svg+xml")
        badge.save()
        badge.refresh_from_db()
        self.assertTrue(badge.image.name.endswith(".svg"))
        self.assertTrue(badge.image.storage.exists(badge.image.name))

    def test_small_png_keeps_its_name(self):
        self.profile.photo = SimpleUploadedFile("me.png", _png_bytes(), content_type="image/png")
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.photo.name.endswith(".png"))

    def test_legacy_raster_key_survives_an_unrelated_save(self):
        # The guard runs on every save; a stored key it cannot decode but that is
        # served as an inert image type must be left alone.
        stored = self.profile.photo.storage.save("profile_photos/old.bmp", io.BytesIO(b"not-decodable"))
        Profile.objects.filter(pk=self.profile.pk).update(photo=stored)
        self.profile.refresh_from_db()
        self.profile.city = "Brno"
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.photo.name, stored)
        self.assertTrue(self.profile.photo.storage.exists(stored))
