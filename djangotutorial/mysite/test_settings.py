"""Settings overrides used by the test runner.

The historic migrations (esp. 0001_initial) contain CharField columns without
`max_length` that Postgres tolerates as TEXT but SQLite rejects. To keep tests
fast and portable (CI, local dev), we skip migration replay entirely and let
Django build tables from the current model definitions. Production uses
Postgres + the migration history; that path is untouched.

Run:
    DJANGO_SETTINGS_MODULE=mysite.test_settings python3 manage.py test
"""
import os
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from .settings import *  # noqa: F401,F403,E402

# Skip all app migrations — `manage.py test` will create tables from models.
class _SkipMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = _SkipMigrations()

# Email backend that captures messages in `django.core.mail.outbox` instead
# of actually sending them. Standard Django convention for tests.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Always disable any leftover DEBUG side-effects.
DEBUG = False
