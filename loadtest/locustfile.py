"""Load test for the GameOfLive API and media serving.

The question this is built to answer: at what concurrency does the app stop
coping, and is the limit the API or the media files?

Media is currently served by Django itself (`django.views.static.serve` in
mysite/urls.py), which occupies a worker for the whole file transfer. The
hypothesis is that images — not API calls — are the binding constraint. So
every task is tagged `api` or `media` and the two can be run separately:

    --tags api      API only, no images
    --tags media    images only
    (no tags)       both, i.e. what a real visitor does

Run against gunicorn, never `manage.py runserver` — the dev server's
concurrency model is nothing like production and the numbers would be
meaningless. See README.md.
"""
import os
import random
from urllib.parse import urlparse

import requests
from locust import HttpUser, between, constant, events, tag, task

# Realistic pacing (people read a page before clicking) vs. saturation mode.
#
# With think-time, N users produce roughly N/3 requests per second — that
# measures whether the site feels fast at a given audience size, but it will
# never find the breaking point. Set FLAT_OUT=1 to remove the pauses and push
# until something gives; that number is the actual capacity ceiling.
FLAT_OUT = os.getenv("FLAT_OUT") == "1"

# Discovered once at test start and shared by every simulated user, so the
# catalogue lookups don't themselves become part of the measured load.
CATALOGUE = {"slugs": [], "images": [], "player_ids": []}


@events.test_start.add_listener
def discover_catalogue(environment, **_kwargs):
    """Pull real slugs, player ids and image URLs off the target host.

    Hitting one hard-coded event would measure the cache, not the app, so
    tasks pick randomly from whatever the target actually has.
    """
    host = environment.host.rstrip("/")
    try:
        events_payload = requests.get(f"{host}/api/v1/events/", timeout=30).json()
    except Exception as exc:  # noqa: BLE001 — surface it and stop, don't half-run
        print(f"!! catalogue discovery failed against {host}: {exc}")
        return

    for event in events_payload.get("events", []):
        if event.get("slug"):
            CATALOGUE["slugs"].append(event["slug"])
        for field in ("image", "logo"):
            if event.get(field):
                CATALOGUE["images"].append(urlparse(event[field]).path)

    try:
        gallery = requests.get(f"{host}/api/v1/gallery/?limit=50", timeout=30).json()
        for photo in gallery.get("photos", []):
            for field in ("url", "url_mobile"):
                if photo.get(field):
                    CATALOGUE["images"].append(urlparse(photo[field]).path)
    except Exception as exc:  # noqa: BLE001
        print(f"!! gallery discovery failed: {exc}")

    try:
        board = requests.get(f"{host}/api/v1/leaderboard/", timeout=30).json()
        for entry in board.get("entries", [])[:100]:
            if entry.get("id"):
                CATALOGUE["player_ids"].append(entry["id"])
    except Exception as exc:  # noqa: BLE001
        print(f"!! leaderboard discovery failed: {exc}")

    CATALOGUE["images"] = list(dict.fromkeys(CATALOGUE["images"]))
    print(
        f"catalogue: {len(CATALOGUE['slugs'])} events, "
        f"{len(CATALOGUE['images'])} images, "
        f"{len(CATALOGUE['player_ids'])} players"
    )
    if not CATALOGUE["images"]:
        print("!! no images found — the `media` tag will do nothing")


class Visitor(HttpUser):
    """An anonymous visitor browsing the site.

    Task weights approximate a real session: the landing page is hit most,
    then the event list, then a few detail pages. Nobody opens the leaderboard
    twenty times in a row.
    """

    wait_time = constant(0) if FLAT_OUT else between(1, 5)

    def _get(self, path, name):
        """GET that separates 'throttled' from 'broken' in the results.

        Locust counts any non-2xx as a failure, which would lump the rate
        limiter's 429s in with real 500s and make the output unreadable.
        """
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code == 429:
                response.failure("429 throttled (rate limit, not a fault)")
            elif response.status_code >= 500:
                response.failure(f"{response.status_code} server error")
            elif response.status_code >= 400:
                response.failure(f"{response.status_code}")
            else:
                response.success()
            return response

    # ---------------------------------------------------------------- API --

    @tag("api")
    @task(10)
    def home(self):
        # The landing page fires both of these on load.
        self._get("/api/v1/stats/", name="API /stats")
        self._get("/api/v1/hero/", name="API /hero")

    @tag("api")
    @task(8)
    def events_list(self):
        self._get("/api/v1/events/", name="API /events")

    @tag("api")
    @task(6)
    def event_detail(self):
        if not CATALOGUE["slugs"]:
            return
        slug = random.choice(CATALOGUE["slugs"])
        self._get(f"/api/v1/events/{slug}/", name="API /events/[slug]")

    @tag("api")
    @task(5)
    def leaderboard(self):
        self._get("/api/v1/leaderboard/", name="API /leaderboard")

    @tag("api")
    @task(3)
    def gallery(self):
        offset = random.choice([0, 12, 24])
        self._get(f"/api/v1/gallery/?limit=12&offset={offset}", name="API /gallery")

    @tag("api")
    @task(2)
    def player_detail(self):
        if not CATALOGUE["player_ids"]:
            return
        player_id = random.choice(CATALOGUE["player_ids"])
        self._get(f"/api/v1/players/{player_id}/", name="API /players/[id]")

    @tag("api")
    @task(2)
    def spa_shell(self):
        # A cold visitor loads the HTML shell before any API call.
        self._get("/", name="SPA shell /")

    # -------------------------------------------------------------- MEDIA --

    @tag("media")
    @task(14)
    def load_images(self):
        """Fetch several images, the way opening a page with a grid does.

        Weighted highest on purpose: one page view produces one API call and
        a dozen image requests. That ratio is the whole point of the test.
        """
        if not CATALOGUE["images"]:
            return
        sample_size = min(6, len(CATALOGUE["images"]))
        for path in random.sample(CATALOGUE["images"], sample_size):
            self._get(path, name="MEDIA /media/[image]")
