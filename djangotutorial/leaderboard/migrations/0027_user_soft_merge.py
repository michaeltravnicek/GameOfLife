"""Soft merge for leaderboard players.

`merged_into` marks a player that was folded into another one. The row stays:
undoing a bad merge is an UPDATE, not a database restore. See
`leaderboard/merging.py`.
"""

import django.db.models.deletion
import django.db.models.manager
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaderboard', '0026_drop_user_phone_number'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='user',
            options={'base_manager_name': 'all_objects', 'default_manager_name': 'all_objects'},
        ),
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('all_objects', django.db.models.manager.Manager()),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='merged_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='merged_into',
            field=models.ForeignKey(blank=True, help_text='Vyplněné = tento hráč byl sloučen do jiného a nezobrazuje se.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='merged_from', to='leaderboard.user'),
        ),
    ]
