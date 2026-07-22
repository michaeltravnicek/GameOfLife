import gc
from datetime import datetime

from django.db import reset_queries
from google.oauth2 import service_account
from googleapiclient.discovery import build

from leaderboard.models import Event, EventFeedback, User, UserToEvent
from leaderboard.sheet_columns import (
    cell,
    header_map,
    is_negative_attendance,
    parse_rating,
)
from leaderboard.utils import parse_event_date_from_name, parse_phone_number

SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]
SERVICE_ACCOUNT_FILE = '../credentials.json'


def insert_event(sheet_id: str, sheet: dict):
    sheet_list_id = str(sheet["properties"]["sheetId"]) 
    sheet_name = sheet["properties"]["title"]

    event, created = Event.objects.get_or_create(
        sheet_id=sheet_id,
        sheet_list_id=sheet_list_id,
        defaults={
            "name": sheet_name,
            "points": 50,
            "place": "Brno",
            # The event's real date (parsed from the sheet title) — NOT the
            # sync time, which lands the points on the wrong day in profiles.
            "date": parse_event_date_from_name(sheet_name) or datetime.now(),
        }
    )
    if created:
        print("New event")
    return event


def handle_new_user(rec: tuple) -> User | None:
    """
    rec[1] = number, rec[2] = name
    """
    number = parse_phone_number(rec[1])
    if number is None:
        print("Invalid Number!")
        return

    user, created = User.objects.get_or_create(
        number=number,
        defaults={"name": rec[2]}
    )
    if not created:
        print("USER FOUND", user)
    else:
        print(f"Inserted user ID: {user.id}")
    return user


def insert_rec(event: Event, rec: tuple, cols: dict[str, int]):
    user = handle_new_user(rec)
    if user is None:
        return

    # "Zúčastnil/a ses této akce?" == "Ne" -> the person filled the form but did
    # not come. No attendance, no points; their feedback (if any) is not about
    # an event they were at, so skip the row entirely.
    if is_negative_attendance(cell(rec, cols.get("attended"))):
        print(f"Skipping {user} — did not attend")
        return

    points_index = cols.get("points")
    if points_index is not None:
        points = rec[points_index]
    else:
        points = event.points

    ute, created = UserToEvent.objects.get_or_create(
        user=user,
        event=event,
        defaults={"points": points},
    )

    if not created and ute.points != points:
        ute.points = points
        ute.save(update_fields=["points"])

    insert_feedback(event, user, rec, cols)


def insert_feedback(event: Event, user: User, rec: tuple, cols: dict[str, int]):
    """Store the row's rating + comment, when the sheet carries those columns.

    A row with neither a usable rating nor a comment writes nothing — most
    respondents skip the optional free-text box, and an empty feedback row would
    drag the event's average around for no reason.
    """
    rating = parse_rating(cell(rec, cols.get("rating")))
    comment = cell(rec, cols.get("comment"))
    if rating is None and not comment:
        return

    existing = EventFeedback.objects.filter(user=user, event=event).first()

    # Feedback typed on the site is the person's own considered answer; never
    # let a form re-import overwrite it.
    if existing and existing.source == EventFeedback.SOURCE_WEB:
        return

    # Rating is required by the model, so a comment-only row needs a rating to
    # exist. Keep whatever was already stored rather than inventing one.
    if rating is None:
        if existing is None:
            return
        rating = existing.rating

    EventFeedback.objects.update_or_create(
        user=user,
        event=event,
        defaults={
            "rating": rating,
            "comment": comment,
            "source": EventFeedback.SOURCE_FORM,
        },
    )


def handle_attendance(sheet_id: str, sheet_list_id: str, records: list[tuple[str]], run_all: bool):
    try:
        event = Event.objects.get(sheet_id=sheet_id, sheet_list_id=sheet_list_id)
    except Event.DoesNotExist:
        return

    if not records:
        return

    cols = header_map(records[0])

    # The incremental slice below assumes row N of the sheet is the Nth
    # attendance row. Feedback breaks that: people edit a rating in days after
    # the event, on a row that was already imported, and "Ne" rows now produce
    # no UserToEvent at all so the count drifts from the row offset. When the
    # sheet carries feedback columns, rescan everything — insert_rec is
    # idempotent and these sheets are one page per event.
    has_feedback_cols = "rating" in cols or "comment" in cols

    if run_all or has_feedback_cols:
        new_records = records[1:]
    else:
        existing_count = UserToEvent.objects.filter(event=event).count()
        new_records = records[1+existing_count:] if existing_count < len(records) else []

    for rec in new_records:
        insert_rec(event, rec, cols)


def main(run_all: bool):
    print("Running")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    service = build('drive', 'v3', credentials=creds)
    query = "mimeType='application/vnd.google-apps.spreadsheet' and trashed = false"

    sheets = service.files().list(
        q=query,
        pageSize=100,
        fields="files(id, name)"
    ).execute()

    service_sheets = build("sheets", "v4", credentials=creds)
    for sheet_info in sheets.get("files", []):
        sheet_id = sheet_info["id"]
    
        spreadsheet = service_sheets.spreadsheets().get(
            spreadsheetId=sheet_id
        ).execute()

        for sheet_meta in spreadsheet.get("sheets", []):
            title = sheet_meta["properties"]["title"]
            print(f"Processing sheet: {title}")
            insert_event(sheet_id, sheet_meta)
            
            result = service_sheets.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=title
            ).execute()

            sheet_list_id = str(sheet_meta["properties"]["sheetId"]) 
            handle_attendance(sheet_id, sheet_list_id, result.get("values", []), run_all)
            
            del result
            reset_queries()
            gc.collect()

    del service_sheets, sheets, service
    gc.collect()

    # Points changed → drop the leaderboard / stats caches.
    from leaderboard.cache_config import invalidate_points_dependent_caches
    invalidate_points_dependent_caches()


def run_google_sheet_sync(run_all=True):
    """Thin alias for `main`, kept as the named entry point for the sync.

    Previously decorated with django-background-tasks' @background, but no
    `process_tasks` worker was ever run, so the queued task never executed.
    The sync actually runs via `manage.py sync_sheets` (see build.sh).
    """
    main(run_all)
