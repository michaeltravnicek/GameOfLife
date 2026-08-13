"""Re-key EventFeedback from auth user to leaderboard user, rating 1-5 -> 1-10.

Feedback now arrives mostly from the Google Form sync, which identifies people
by phone number (a leaderboard User) and has no auth account to hang off.

Existing rows are carried over via Profile.leaderboard_user. Rows whose author
has no linked leaderboard user cannot be represented in the new shape and are
dropped -- the migration prints how many, so the loss is visible in the deploy
log rather than silent.

Ratings were given on a 1-5 scale and are doubled: a 5 meant "best possible",
which is 10 on the new scale. Keeping them as-is would silently re-read every
past top rating as mediocre.
"""
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def forwards(apps, schema_editor):
    EventFeedback = apps.get_model("leaderboard", "EventFeedback")
    Profile = apps.get_model("accounts", "Profile")

    lb_by_auth = dict(
        Profile.objects
        .exclude(leaderboard_user__isnull=True)
        .values_list("user_id", "leaderboard_user_id")
    )

    kept, dropped = 0, 0
    for fb in EventFeedback.objects.all():
        lb_id = lb_by_auth.get(fb.auth_user_id)
        if lb_id is None:
            fb.delete()
            dropped += 1
            continue
        fb.user_id = lb_id
        fb.rating = min(fb.rating * 2, 10)
        fb.save(update_fields=["user", "rating"])
        kept += 1

    if kept or dropped:
        print(f"  EventFeedback: {kept} migrated, {dropped} dropped (no leaderboard user)")


def backwards(apps, schema_editor):
    """Best-effort reverse: leaderboard user -> its linked auth user, rating halved."""
    EventFeedback = apps.get_model("leaderboard", "EventFeedback")
    Profile = apps.get_model("accounts", "Profile")

    auth_by_lb = dict(
        Profile.objects
        .exclude(leaderboard_user__isnull=True)
        .values_list("leaderboard_user_id", "user_id")
    )
    for fb in EventFeedback.objects.all():
        auth_id = auth_by_lb.get(fb.user_id)
        if auth_id is None:
            fb.delete()
            continue
        fb.auth_user_id = auth_id
        fb.rating = max(1, round(fb.rating / 2))
        fb.save(update_fields=["auth_user", "rating"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_profile_role"),
        ("leaderboard", "0016_alter_event_date_alter_event_survey_url_and_more"),
    ]

    operations = [
        # Drop old guards first: the 1-5 check would reject the doubled ratings,
        # and the (auth_user, event) uniqueness blocks nothing useful once the
        # key moves.
        migrations.RemoveConstraint(
            model_name="eventfeedback",
            name="feedback_rating_1_5",
        ),
        migrations.AlterUniqueTogether(
            name="eventfeedback",
            unique_together=set(),
        ),
        # Nullable for the data pass; tightened below.
        migrations.AddField(
            model_name="eventfeedback",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="feedbacks",
                to="leaderboard.user",
            ),
        ),
        migrations.AddField(
            model_name="eventfeedback",
            name="source",
            field=models.CharField(
                choices=[("web", "Web"), ("form", "Google Form")],
                default="web",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="eventfeedback",
            name="rating",
            field=models.PositiveSmallIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10),
                ]
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="eventfeedback",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="feedbacks",
                to="leaderboard.user",
            ),
        ),
        migrations.RemoveField(
            model_name="eventfeedback",
            name="auth_user",
        ),
        migrations.AlterUniqueTogether(
            name="eventfeedback",
            unique_together={("user", "event")},
        ),
        migrations.AddConstraint(
            model_name="eventfeedback",
            constraint=models.CheckConstraint(
                check=models.Q(("rating__gte", 1), ("rating__lte", 10)),
                name="feedback_rating_1_10",
            ),
        ),
    ]
