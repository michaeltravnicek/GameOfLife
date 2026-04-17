from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify
import django.db.models.deletion


def backfill_event_slugs(apps, schema_editor):
    Event = apps.get_model("leaderboard", "Event")
    used = set()
    for event in Event.objects.all().order_by("pk"):
        if event.slug:
            used.add(event.slug)
            continue
        base = slugify(event.name) or "akce"
        slug = base
        n = 2
        while slug in used or Event.objects.filter(slug=slug).exclude(pk=event.pk).exists():
            slug = f"{base}-{n}"
            n += 1
        event.slug = slug
        used.add(slug)
        event.save(update_fields=["slug"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("leaderboard", "0004_lastupdate"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="slug",
            field=models.SlugField(blank=True, max_length=280, null=True, unique=True),
        ),
        migrations.RunPython(backfill_event_slugs, noop_reverse),
        migrations.CreateModel(
            name="EventRSVP",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rsvps", to="leaderboard.event")),
                ("auth_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rsvps", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("auth_user", "event")}},
        ),
        migrations.CreateModel(
            name="EventFeedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField()),
                ("comment", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feedbacks", to="leaderboard.event")),
                ("auth_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feedbacks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("auth_user", "event")}},
        ),
    ]
