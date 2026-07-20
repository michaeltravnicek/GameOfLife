"""Model hygiene: FK renames, description -> TextField, created/updated stamps.

RenameField is written by hand on purpose — a non-interactive `makemigrations`
would emit RemoveField + AddField for a rename and silently drop the column's
data. RenameField is a plain SQL column rename, so nothing is lost.

  ImageToEvent.event_id -> event   (the old name produced a DB column
                                    `event_id_id` and read backwards in queries)
  PhotoLike.user        -> auth_user  (every other auth FK here uses that name)

Timestamps are null=True: the real creation time of pre-existing rows is
unknown, and inventing one (e.g. "now") would be a lie in the data.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0017_eventfeedback_leaderboard_user"),
    ]

    operations = [
        # --- renames (data-preserving column renames) ---
        migrations.RenameField(
            model_name="imagetoevent", old_name="event_id", new_name="event",
        ),
        migrations.AlterField(
            model_name="imagetoevent",
            name="event",
            field=models.ForeignKey(
                on_delete=models.CASCADE, related_name="official_images",
                to="leaderboard.event",
            ),
        ),
        # unique_together references the old field name — clear it before the
        # rename lands, then re-declare it with the new name.
        migrations.AlterUniqueTogether(name="photolike", unique_together=set()),
        migrations.RenameField(
            model_name="photolike", old_name="user", new_name="auth_user",
        ),
        migrations.AlterUniqueTogether(
            name="photolike", unique_together={("photo", "auth_user")},
        ),

        # --- widening / additions ---
        migrations.AlterField(
            model_name="event",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="event",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="event",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
