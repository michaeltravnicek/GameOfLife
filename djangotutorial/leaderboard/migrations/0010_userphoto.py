from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0009_season_event_logo_event_rules"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="user_photos/")),
                ("caption", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("auth_user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="gallery_photos",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("event", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="user_photos",
                    to="leaderboard.event",
                )),
            ],
        ),
    ]
