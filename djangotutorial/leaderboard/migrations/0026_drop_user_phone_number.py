"""Drop LeaderboardUser.number (the phone) and add LeaderboardUser.email.

The number existed only as the key the Google Sheets sync used to match a form
response to a player. A phone number collected for no other purpose is data with
no purpose, so it goes. Identity moves to the e-mail the form collects, with the
name as the fallback for sheets that predate it — see
``leaderboard/tasks.py:resolve_player``.

⚠ THIS DESTROYS DATA AND CANNOT BE REVERSED. `number` was unique and NOT NULL, so
there is nothing to rebuild it from — unapplying this migration would fail on the
first existing row. Before running it in production:

    /usr/bin/python3 manage.py export_player_numbers

which writes (id, number, name) to a gitignored CSV. After that, only a Render
database backup still has the numbers.

Nothing else needs a data migration: attendance, badges and feedback all point at
User by primary key, and those keys do not move.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaderboard', '0025_drop_event_logo'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='user',
            name='user_number_9_digits',
        ),
        migrations.RemoveField(
            model_name='user',
            name='number',
        ),
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, help_text='E-mail z formuláře — spojuje odpovědi téhož člověka. Prázdné u starších hráčů.', max_length=254, null=True, unique=True),
        ),
    ]
