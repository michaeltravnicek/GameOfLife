import gc
import re
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
from leaderboard.utils import parse_event_date_from_name

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


# Old sheets are "Timestamp | Telefon | Jméno a příjmení | …" with no header we
# recognise for the name column. The phone is not read any more (the column may
# still be there in historical sheets; we simply ignore it), but the name is
# still needed, so fall back to its fixed position.
LEGACY_NAME_INDEX = 2


def normalize_name(raw: str) -> str:
    """Trim and collapse inner whitespace — "Jan  Novák " and "Jan Novák" are one person."""
    return re.sub(r"\s+", " ", str(raw or "")).strip()


def resolve_player(rec: tuple, cols: dict[str, int]) -> User | None:
    """Find (or create) the leaderboard player a form response belongs to.

    E-mail first: it is the only value in the sheet that is genuinely one person,
    and it is the same key the site account uses. Forms with "Collect email
    addresses" switched on provide it.

    Name second, for the sheets that predate that — and they are most of the
    archive. Name matching is case-insensitive and whitespace-tolerant, but it
    cannot tell two namesakes apart; that is the price of not keeping a phone
    number around purely as a join key, and it is the reason e-mail is preferred
    whenever the column exists.

    Returns None for a row with neither, which is a row we cannot attribute to
    anyone — skipping it is better than inventing a player.
    """
    from .merging import resolve_player_id

    email = cell(rec, cols.get("email")).lower() or None
    name = normalize_name(cell(rec, cols.get("name", LEGACY_NAME_INDEX)))

    if email:
        # all_objects, then resolve: the row that owns this address may since
        # have been merged into an account's player. Writing to the merged-away
        # row would park the points off the leaderboard, where nobody sees them.
        user = User.all_objects.filter(email=email).first()
        if user:
            return resolve_player_id(user.pk)
        # This person may already exist from a name-only sheet. Adopt that row
        # instead of starting a second one — otherwise the same human ends up
        # with their points split across two players.
        if name:
            # Active rows only: a merged player must not be given an e-mail, it
            # would resurrect it as a match target for every later sync.
            user = User.objects.filter(
                email__isnull=True, name__iexact=name,
            ).order_by("id").first()
            if user:
                user.email = email
                user.save(update_fields=["email"])
                print(f"Linked existing player {user} to {email}")
                return user
        return User.objects.create(email=email, name=name or email)

    if not name:
        print("Row has neither e-mail nor name — skipping")
        return None

    user = User.objects.filter(name__iexact=name).order_by("id").first()
    if user:
        return user
    # No live player by that name — but a merged one may still carry it, and an
    # admin has already ruled that that name is this account. Honour the ruling
    # instead of recreating the row they just cleared off the queue.
    merged = User.all_objects.filter(
        name__iexact=name, merged_into__isnull=False).order_by("id").first()
    if merged:
        return resolve_player_id(merged.pk)
    return User.objects.create(name=name)


def insert_rec(event: Event, rec: tuple, cols: dict[str, int]):
    user = resolve_player(rec, cols)
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
    # Each attendance row now evicts the caches on save (UserToEvent.save), which
    # is right for a single admin edit and wrong for a few thousand rows — the
    # season family is evicted with a Redis SCAN. Suspend it and evict once below.
    from leaderboard.cache_config import (
        invalidate_points_dependent_caches, suspend_points_cache_invalidation,
    )
    with suspend_points_cache_invalidation():
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

    # Points changed → drop the leaderboard / stats caches. This is the one
    # eviction for the whole run (see suspend_points_cache_invalidation).
    invalidate_points_dependent_caches()


def run_google_sheet_sync(run_all=True):
    """Thin alias for `main`, kept as the named entry point for the sync.

    Previously decorated with django-background-tasks' @background, but no
    `process_tasks` worker was ever run, so the queued task never executed.
    The sync actually runs via `manage.py sync_sheets` (see build.sh).
    """
    main(run_all)
