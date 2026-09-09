"""Create the initial superuser from DJANGO_SUPERUSER_* env vars.

build.sh runs this once against a fresh database. On an existing database the
account is already there and this is a no-op.

There is deliberately NO default password. An unset DJANGO_SUPERUSER_PASSWORD
used to fall back to "adminpassword", so any deploy that forgot the variable
stood up an `admin` / `adminpassword` account on the obscured admin URL — the
first credential any scanner tries, and well inside the axes lockout budget
(audit 2026-08-26, critical). Now:

  * running in a terminal with no password set → hand off to Django's interactive
    `createsuperuser` (local dev convenience);
  * running non-interactively (the deploy) with no password set → fail the build.

The password is also run through AUTH_PASSWORD_VALIDATORS, which
create_superuser() otherwise skips.
"""
import os
import sys

import django
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if User.objects.filter(username=username).exists():
    print(f"Superuser '{username}' already exists.")
    sys.exit(0)

if not password:
    if sys.stdin.isatty():
        call_command("createsuperuser", username=username, email=email)
        sys.exit(0)
    sys.exit(
        f"Refusing to create superuser '{username}': DJANGO_SUPERUSER_PASSWORD is "
        "not set. Set it in the environment and re-run."
    )

try:
    validate_password(password)
except ValidationError as exc:
    sys.exit("DJANGO_SUPERUSER_PASSWORD rejected: " + "; ".join(exc.messages))

User.objects.create_superuser(username=username, email=email, password=password)
print(f"Superuser '{username}' created.")
