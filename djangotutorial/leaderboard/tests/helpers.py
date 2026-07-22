"""Shared fixtures for the leaderboard test suite."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import Profile
from leaderboard.models import User as LeaderboardUser

# Brno reference point used by all check-in tests.
BRNO_LAT = 49.1951
BRNO_LON = 16.6068


def make_image_upload(name="test.png", size=(8, 8), image_format="PNG",
                      content_type="image/png"):
    """A real, decodable image file for upload tests.

    `validate_upload` parses the header with PIL rather than trusting the
    browser-supplied content type, so placeholder bytes like b"dummy" are
    (correctly) rejected as "not a valid image" and can't be used as fixtures.
    """
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format=image_format)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def make_profile_for(auth_user, *, number):
    """Link `auth_user` to a fresh LeaderboardUser via a Profile."""
    lb_user = LeaderboardUser.objects.create(number=number, name=f"Tester {number}")
    profile, _ = Profile.objects.get_or_create(user=auth_user)
    profile.leaderboard_user = lb_user
    profile.save()
    return lb_user
