"""
WSGI config for mysite project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

# manage.py loads .env, but this entry point did not — so anything started
# through gunicorn (production, and any local load test) came up without
# DATABASE_URL and fell back to Django's dummy database backend, 500ing on the
# first query that missed the cache.
#
# In production this is a no-op: Render injects real environment variables and
# there is no .env file. load_dotenv does not override variables that are
# already set, so the platform's values always win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

application = get_wsgi_application()
