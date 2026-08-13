"""Test helpers shared by the leaderboard and accounts suites.

Lives in `mysite` rather than in either app because the thing it stands in for
-- the built SPA shell -- belongs to the project, not to one app.
"""
import os
import tempfile
from unittest.mock import patch

# A minimal stand-in for the built index.html. Only the parts tests assert on
# are real: the <div id="root"> the SPA mounts into, and a <title> for og.py to
# replace.
SPA_SHELL = (
    "<!doctype html><html><head><title>Game of Live</title></head>"
    '<body><div id="root"></div></body></html>'
)


class SpaShellMixin:
    """Give `react_index` something to serve, independent of any real build.

    `mysite.views._resolve_index_path` looks for staticfiles/react/index.html,
    falls back to frontend/dist/index.html, and raises Http404 if neither
    exists. Both are build artifacts and both are gitignored, so in a fresh
    checkout -- which is exactly what CI runs -- neither is there and every
    request for a page route 404s as plain text.

    That made two tests fail in CI while passing locally, purely because a stale
    frontend/dist happened to be lying around here. Any test that expects Django
    to serve the SPA must bring its own shell rather than hope a build exists.
    """

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        index_path = os.path.join(tmp.name, "index.html")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(SPA_SHELL)
        patcher = patch("mysite.views._resolve_index_path", return_value=index_path)
        patcher.start()
        self.addCleanup(patcher.stop)
