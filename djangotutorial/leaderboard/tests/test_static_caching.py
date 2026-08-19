"""The SPA bundle must be cacheable for years, and only the bundle.

Vite writes a content hash into every chunk filename, which is what makes an
aggressive cache safe: a new build produces new names, so nothing ever has to be
invalidated. WhiteNoise cannot work that out on its own here — it only tests for
immutability under STATIC_URL (see whitenoise/middleware.py: `if not
url.startswith(self.static_prefix): return False`), and this project serves the
build from WHITENOISE_ROOT at the site root instead. Every chunk therefore went
out with the default `max-age=60`, measured on production, and Cloudflare copied
that TTL to the edge.

WHITENOISE_IMMUTABLE_FILE_TEST closes that gap. It is a regex, and it is the
only thing between a filename and a ten-year cache entry that no deploy can
recall — so it gets tested in both directions: it must match what Vite actually
emits, and it must not match anything whose name can be reused.
"""
import re

from django.test import SimpleTestCase

# Copied from settings (the production branch, which test_settings does not
# execute). Kept in sync by test_the_pattern_matches_the_shipped_settings below.
IMMUTABLE_RE = r"^/assets/.+-[A-Za-z0-9_-]{8,}\.(js|css)$"

# Real filenames from a `npm run build` of this repo.
HASHED = [
    "/assets/index-CVUoYw2C.js",
    "/assets/index-DunOkO-W.css",
    "/assets/jsx-runtime-C7oxC63R.js",
    "/assets/chunk-62JRHF6Z-Uzrd0E6Q.js",   # a hyphen inside the name as well
    "/assets/EventDetailPage-Cc5VE_Rc.js",  # underscore in the hash
    "/assets/EventLocationMap-EyjR-uKP.js",  # hyphen in the hash
    "/assets/ToastProvider-BopyEzBd.css",
]

# Anything whose name a later build can reuse with different bytes. A ten-year
# `immutable` on one of these is unrecallable: browsers do not revalidate it.
MUTABLE = [
    "/index.html",                    # names the current hashes — never immutable
    "/assets/index.js",               # no hash at all
    "/assets/style.css",
    "/img/GOL_main_logo_pink.webp",   # `npm run images` output, stable name
    "/fonts/IBMPlexMono-Italic.ttf",
    "/site.webmanifest",
    "/media/event_images/party.webp",  # uploads are not static at all
    "/api/v1/events/",
]


class ImmutableAssetPatternTests(SimpleTestCase):
    def setUp(self):
        self.pattern = re.compile(IMMUTABLE_RE)

    def test_matches_every_hashed_chunk_vite_emits(self):
        for url in HASHED:
            with self.subTest(url=url):
                self.assertRegex(url, self.pattern)

    def test_matches_nothing_whose_name_can_be_reused(self):
        for url in MUTABLE:
            with self.subTest(url=url):
                self.assertNotRegex(url, self.pattern)

    def test_the_pattern_matches_the_shipped_settings(self):
        """Guards against this file drifting from the value actually deployed.

        The setting lives inside `if not DEBUG:`, which the test settings do not
        take, so it cannot simply be imported — read it out of the source.
        """
        from pathlib import Path

        from django.conf import settings

        source = (Path(settings.BASE_DIR) / "mysite" / "settings.py").read_text(encoding="utf-8")
        match = re.search(r'WHITENOISE_IMMUTABLE_FILE_TEST = r"([^"]+)"', source)
        self.assertIsNotNone(match, "WHITENOISE_IMMUTABLE_FILE_TEST is gone from settings")
        self.assertEqual(match.group(1), IMMUTABLE_RE)
