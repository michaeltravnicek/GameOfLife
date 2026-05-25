import gc
from datetime import datetime

from background_task import background
from django.db import reset_queries
from google.oauth2 import service_account
from googleapiclient.discovery import build

from leaderboard.models import Event, User, UserToEvent
from leaderboard.utils import parse_phone_number

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
            "date": datetime.now(),
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


def insert_rec(event: Event, rec: tuple, points_index: int | None):
    user = handle_new_user(rec)
    if user is None:
        return

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


def handle_attendance(sheet_id: str, sheet_list_id: str, records: list[tuple[str]], run_all: bool):
    try:
        event = Event.objects.get(sheet_id=sheet_id, sheet_list_id=sheet_list_id)
    except Event.DoesNotExist:
        return

    existing_count = UserToEvent.objects.filter(event=event).count()
    index = None
    for i, meta in enumerate(records[0]):
        if meta.lower() == "body":
            index = i
                
    if run_all:
        new_records = records[1:] 
    else:
        new_records = records[1+existing_count:] if existing_count < len(records) else []
    

    for rec in new_records:
        insert_rec(event, rec, index)


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


@background(schedule=60)
def run_google_sheet_sync(run_all=True):
    main(run_all)
