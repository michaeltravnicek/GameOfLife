"""One-shot export of the phone numbers before the migration drops them.

Run this BEFORE migrating (leaderboard/migrations/0026), because afterwards the
column is gone and the only copy left is a Render database backup.

Reads the column with raw SQL on purpose: the model no longer has a ``number``
field, and a command that referenced it would not import at all. Raw SQL also
means this still works against a database that has not been migrated yet, which
is exactly the situation it is for.

⚠ The output file is a list of names and phone numbers — the most sensitive file
this repo can produce. The default filename is gitignored (``player_numbers_*.csv``);
keep it off shared drives too, and delete it once you are sure nothing needed the
numbers. Holding an export "just in case" forever is its own GDPR problem.
"""
import csv
from datetime import date

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Export leaderboard player phone numbers to CSV before they are dropped."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o",
            default=f"player_numbers_{date.today().isoformat()}.csv",
            help="Destination CSV path (default: player_numbers_<today>.csv).",
        )

    def handle(self, *args, **options):
        path = options["output"]

        with connection.cursor() as cursor:
            columns = {
                col.name for col in connection.introspection.get_table_description(
                    cursor, "leaderboard_user",
                )
            }
            if "number" not in columns:
                self.stdout.write(self.style.WARNING(
                    "leaderboard_user has no `number` column — the migration has "
                    "already run and there is nothing left to export. Restore a "
                    "database backup if you need the numbers."
                ))
                return

            cursor.execute(
                "SELECT id, number, name FROM leaderboard_user ORDER BY id"
            )
            rows = cursor.fetchall()

        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "number", "name"])
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"Exported {len(rows)} players to {path}"
        ))
        self.stdout.write(self.style.WARNING(
            "This file contains phone numbers. Store it somewhere private and "
            "delete it when you no longer need it."
        ))
