from django.db import migrations


DEFAULT_QUESTIONS = [
    (1, "Co o tobě nikdo neví?"),
    (2, "Co by o tobě měli všichni vědět?"),
    (3, "Jak bys se popsal v jedné větě?"),
    (4, "Jaká byla tvoje první akce s Gameoflife?"),
]


def create_questions(apps, schema_editor):
    ProfileQuestion = apps.get_model("leaderboard", "ProfileQuestion")
    for order, text in DEFAULT_QUESTIONS:
        ProfileQuestion.objects.get_or_create(text=text, defaults={"order": order})


def delete_questions(apps, schema_editor):
    ProfileQuestion = apps.get_model("leaderboard", "ProfileQuestion")
    texts = [text for _, text in DEFAULT_QUESTIONS]
    ProfileQuestion.objects.filter(text__in=texts).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("leaderboard", "0007_event_capacity"),
    ]

    operations = [
        migrations.RunPython(create_questions, delete_questions),
    ]
