"""Drop Event.logo / Event.logo_scale, now that 0024 moved them onto Badge.

Separate from 0024 on purpose: 0024 writes Event.badge_id, and Postgres will not
ALTER a table inside a transaction that already has pending trigger events from
DML on it -- the two together fail with "cannot ALTER TABLE ... because it has
pending trigger events". One migration per transaction sidesteps that.

Deploy note: this is the point of no return for the artwork. 0024 alone is
harmless (it only adds rows), so if the badge mapping ever looks wrong, stop
before this one.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0024_event_logo_into_badge"),
    ]

    operations = [
        migrations.RemoveField(model_name="event", name="logo"),
        migrations.RemoveField(model_name="event", name="logo_scale"),
        # help_text only -- the column itself is unchanged.
        migrations.AlterField(
            model_name="event",
            name="badge",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="events",
                to="leaderboard.badge",
                help_text="Logo akce — zároveň odznak, který účastníci získají do sbírky.",
            ),
        ),
    ]
