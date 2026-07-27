"""Guards for the 0024 logo→badge helpers.

The migration itself can't be replayed in a test: its reverse deliberately
raises (several events end up sharing one Badge, so per-event artwork cannot be
reconstructed), and a test would have to migrate backwards past it to set up.

What *can* go wrong silently is the grouping key. If `_digest` returned
something per-file rather than per-content, the migration would create 135
badges instead of 7 and the duplication it exists to remove would survive the
whole exercise. That is what these cover.
"""
import importlib
import os
import tempfile

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase

from leaderboard.models import Badge

_mod = importlib.import_module("leaderboard.migrations.0024_event_logo_into_badge")


class _StoredFile:
    """Minimal stand-in for a FieldFile: `.storage` + `.name` is all _digest uses."""

    def __init__(self, storage, name):
        self.storage = storage
        self.name = name


class DigestTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = FileSystemStorage(location=self.tmp.name)

    def _write(self, name, content):
        self.storage.save(name, ContentFile(content))
        return _StoredFile(self.storage, name)

    def test_same_bytes_under_different_names_share_a_digest(self):
        """The real case: Django's collision suffix (`logo_66oY4ex.svg`) is the
        only difference between 72 copies of one logo."""
        a = self._write("logo.svg", b"<svg/>")
        b = self._write("logo_66oY4ex.svg", b"<svg/>")
        self.assertEqual(_mod._digest(a), _mod._digest(b))

    def test_different_bytes_do_not_collapse(self):
        a = self._write("one.svg", b"<svg id='a'/>")
        b = self._write("two.svg", b"<svg id='b'/>")
        self.assertNotEqual(_mod._digest(a), _mod._digest(b))

    def test_missing_file_returns_none_instead_of_raising(self):
        """A broken reference must not abort the deploy mid-migration."""
        self.assertIsNone(_mod._digest(_StoredFile(self.storage, "gone.svg")))

    def test_unreadable_files_do_not_merge_with_each_other(self):
        """_digest returning None for two different missing files would merge
        them under one key; the migration falls back to the name for exactly
        this reason. Assert the fallback keys differ."""
        missing_a = _StoredFile(self.storage, "gone-a.svg")
        missing_b = _StoredFile(self.storage, "gone-b.svg")
        key_a = _mod._digest(missing_a) or f"name:{missing_a.name}"
        key_b = _mod._digest(missing_b) or f"name:{missing_b.name}"
        self.assertNotEqual(key_a, key_b)


class UniqueSlugTests(TestCase):
    """Historical models have no methods, so the migration rebuilds the slug
    logic Badge.save() would normally apply."""

    def test_plain_name(self):
        self.assertEqual(_mod._unique_slug(Badge, "Karaoke Tour"), "karaoke-tour")

    def test_collisions_get_suffixed(self):
        Badge.objects.create(name="Karaoke", slug="karaoke")
        Badge.objects.create(name="Karaoke", slug="karaoke-2")
        self.assertEqual(_mod._unique_slug(Badge, "Karaoke"), "karaoke-3")

    def test_unsluggable_name_still_yields_a_slug(self):
        # Emoji-only / punctuation-only names slugify to "" — the column is
        # NOT NULL and unique, so a fallback is required.
        self.assertEqual(_mod._unique_slug(Badge, "🎤"), "odznak")
