"""Delete every DRF auth token.

Token authentication was removed with the Capacitor app (see
DEFAULT_AUTHENTICATION_CLASSES in mysite/settings.py). The rows outlive that
change: DRF tokens never expire and are not rotated by a password change, so a
token minted months ago would still be sitting in the table as a credential its
owner has no way to see or revoke. Nothing accepts them any more, but leaving
harvested-and-forgotten secrets in the database is not a state worth keeping.

Irreversible on purpose -- the reverse would have to invent new secrets, and
"restore the credentials we deliberately destroyed" is not a migration anyone
should be able to run by accident.
"""
from django.db import migrations


def purge_tokens(apps, schema_editor):
    # `rest_framework.authtoken` has since left INSTALLED_APPS. On a database
    # that predates that, the table is still there and gets emptied; on a
    # fresh one there is nothing to purge.
    try:
        Token = apps.get_model("authtoken", "Token")
    except LookupError:
        return
    Token.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_profile_gdpr_consent_at_profile_gdpr_consent_version"),
    ]

    operations = [
        migrations.RunPython(purge_tokens, migrations.RunPython.noop),
    ]
