"""Guards in `image_utils.validate_upload` against hostile uploads.

The expensive-to-decode cases matter most: PIL allocates the *decoded* bitmap
(width * height * channels), so a small file can still exhaust the dyno's RAM.
"""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from leaderboard.image_utils import MAX_IMAGE_PIXELS, validate_upload


def _png_bytes(size):
    """Encode a PNG of `size`, bypassing PIL's bomb guard while building it."""
    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        buf = io.BytesIO()
        Image.new("L", size).save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    finally:
        Image.MAX_IMAGE_PIXELS = previous


class ValidateUploadTests(TestCase):
    def test_rejects_decompression_bomb(self):
        # ~1 MB on disk, ~900 megapixels decoded.
        data = _png_bytes((30000, 30000))
        self.assertLess(len(data), 5 * 1024 * 1024, "fixture should be small on disk")
        upload = SimpleUploadedFile("bomb.png", data, content_type="image/png")
        with self.assertRaises(ValueError) as ctx:
            validate_upload(upload)
        self.assertIn("Rozlišení", str(ctx.exception))

    def test_rejects_oversized_resolution_below_pils_own_guard(self):
        # Between 1x and 2x MAX_IMAGE_PIXELS, PIL only warns — this range is
        # caught by our explicit width*height check, not by DecompressionBombError.
        data = _png_bytes((9000, 9000))  # 81 MP
        upload = SimpleUploadedFile("big.png", data, content_type="image/png")
        with self.assertRaises(ValueError) as ctx:
            validate_upload(upload)
        self.assertIn("Rozlišení", str(ctx.exception))

    def test_rejects_non_image_with_forged_content_type(self):
        # Content type is client-supplied, so the header parse is the real check.
        upload = SimpleUploadedFile(
            "evil.png", b"MZ\x90\x00" + b"\x00" * 500, content_type="image/png"
        )
        with self.assertRaises(ValueError):
            validate_upload(upload)

    def test_rejects_oversized_file(self):
        upload = SimpleUploadedFile(
            "big.jpg", b"\x00" * (16 * 1024 * 1024), content_type="image/jpeg"
        )
        with self.assertRaises(ValueError) as ctx:
            validate_upload(upload)
        self.assertIn("příliš velký", str(ctx.exception))

    def test_accepts_normal_photo(self):
        buf = io.BytesIO()
        Image.new("RGB", (4000, 3000), "red").save(buf, format="JPEG", quality=85)
        upload = SimpleUploadedFile("photo.jpg", buf.getvalue(), content_type="image/jpeg")
        validate_upload(upload)  # must not raise

    def test_leaves_file_readable_for_the_caller(self):
        # validate_upload consumes the header; without a rewind the subsequent
        # save() would write a truncated file.
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), "blue").save(buf, format="PNG")
        upload = SimpleUploadedFile("ok.png", buf.getvalue(), content_type="image/png")
        validate_upload(upload)
        self.assertEqual(upload.read(8), b"\x89PNG\r\n\x1a\n")

    def test_limit_is_above_phone_camera_resolution(self):
        # A 48 MP phone photo must not be caught by the bomb guard.
        self.assertGreater(MAX_IMAGE_PIXELS, 48_000_000)
