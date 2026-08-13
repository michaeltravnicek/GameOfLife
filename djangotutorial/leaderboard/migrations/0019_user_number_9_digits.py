"""Require User.number to be a 9-digit Czech phone (100000000-999999999).

Legacy rows from early Sheets syncs hold junk numbers (666, 8778, 355273 ...)
but real attendance and points. Deleting them would destroy leaderboard history,
and their true phone numbers are unknowable, so they are re-numbered into a
reserved placeholder range instead:

    900000000 + id

The 9xx prefix is outside the Czech mobile range (real ones start 6 or 7), which
makes it an unlikely — but NOT guaranteed — free range: this database already
contains some 9xx numbers, so the loop below explicitly skips any value already
taken instead of trusting the prefix. Nothing that worked before breaks: these
numbers were already junk, so they never matched a real person during sync or
registration. Points, attendance and identities are untouched — only the
(already meaningless) identifier changes.

The fix runs BEFORE the constraint is added, so the migration cannot fail
half-way on dirty data. It prints what it changed, so the rewrite is visible in
the deploy log rather than silent.
"""
from django.core import validators
from django.db import migrations, models

_MIN, _MAX = 100_000_000, 999_999_999
_PLACEHOLDER_BASE = 900_000_000


def renumber_invalid(apps, schema_editor):
    User = apps.get_model("leaderboard", "User")

    invalid = list(User.objects.exclude(number__gte=_MIN, number__lte=_MAX).order_by("id"))
    if not invalid:
        return

    used = set(User.objects.values_list("number", flat=True))
    for user in invalid:
        candidate = _PLACEHOLDER_BASE + user.id
        # Stay unique and inside the allowed range even in odd edge cases.
        while candidate in used or not (_MIN <= candidate <= _MAX):
            candidate += 1
        old = user.number
        user.number = candidate
        user.save(update_fields=["number"])
        used.discard(old)
        used.add(candidate)
        print(f"  renumbered user id={user.id} ({user.name!r}): {old} -> {candidate}")
    print(f"  {len(invalid)} user(s) given placeholder numbers (points untouched)")


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0018_rename_fks_add_timestamps"),
    ]

    operations = [
        migrations.RunPython(renumber_invalid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="number",
            field=models.IntegerField(
                unique=True,
                help_text="Telefon bez předvolby — přesně 9 číslic.",
                validators=[
                    validators.MinValueValidator(100000000),
                    validators.MaxValueValidator(999999999),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=models.Q(number__gte=100000000, number__lte=999999999),
                name="user_number_9_digits",
            ),
        ),
    ]
