from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_profile_instagram_profile_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Bez role"),
                    ("admin", "Administrátor"),
                    ("photographer", "Fotograf"),
                ],
                default="",
                help_text=(
                    "Administrátor má přístup do Django adminu a vidí feedbacky. "
                    "Fotograf může nahrávat oficiální fotky k akcím."
                ),
                max_length=20,
            ),
        ),
    ]
