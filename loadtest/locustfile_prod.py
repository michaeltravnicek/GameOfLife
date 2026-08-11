"""Cautious ORIGIN load test against production (behind Cloudflare).

Real visitors mostly hit Cloudflare's edge cache, so a naive test measures
Cloudflare, not the app. Every request here appends a random `_cb` param so
`cf-cache-status` is MISS and the request reaches gunicorn/Postgres on Render.

This is deliberately API-focused and paced by an external stepped ramp that
stops the moment 5xx errors appear — we are probing a *live* site.
"""
import random
from urllib.parse import urlparse

import requests
from locust import HttpUser, between, events, tag, task

CATALOGUE = {"slugs": [], "images": [], "player_ids": []}


def cb():
    return f"_cb={random.randint(1, 2_000_000_000)}"


@events.test_start.add_listener
def discover_catalogue(environment, **_kwargs):
    host = environment.host.rstrip("/")
    try:
        payload = requests.get(f"{host}/api/v1/events/", timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        print(f"!! catalogue discovery failed against {host}: {exc}")
        return
    for event in payload.get("events", []):
        if event.get("slug"):
            CATALOGUE["slugs"].append(event["slug"])
        for field in ("image", "logo"):
            if event.get(field):
                CATALOGUE["images"].append(urlparse(event[field]).path)
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


class Visitor(HttpUser):
    wait_time = between(1, 5)

    def _get(self, path, name):
        sep = "&" if "?" in path else "?"
        url = f"{path}{sep}{cb()}"
        with self.client.get(url, name=name, catch_response=True) as r:
            if r.status_code == 429:
                r.failure("429 throttled")
            elif r.status_code >= 500:
                r.failure(f"{r.status_code} server error")
            elif r.status_code >= 400:
                r.failure(f"{r.status_code}")
            else:
                r.success()
            return r

    @tag("api")
    @task(10)
    def home(self):
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
        pid = random.choice(CATALOGUE["player_ids"])
        self._get(f"/api/v1/players/{pid}/", name="API /players/[id]")


# ── The R2 question ────────────────────────────────────────────────────────
# Media is served by Django itself (mysite/urls.py → django.views.static.serve)
# and the files average ~930 kB. A gunicorn worker is occupied for the whole
# transfer, so the thing to measure is not "how many images per second" but
# "what does downloading images do to the API sitting next to them".
#
# So: MediaUser scales with -u and hammers cache-busted image URLs, while
# ApiProbeUser stays at exactly one user (fixed_count) making a slow, polite
# request every few seconds. The API numbers in the report are then the latency
# a real visitor sees while other people load photos.
#
# One user is deliberate: DEFAULT_THROTTLE_RATES['anon'] is 120/min, so a
# heavier probe would measure the throttle instead of the server.

class MediaUser(HttpUser):
    """Downloads images straight from the origin, one after another."""
    wait_time = between(0.5, 1.5)

    @tag("media")
    @task
    def image(self):
        if not CATALOGUE["images"]:
            return
        path = random.choice(CATALOGUE["images"])
        with self.client.get(f"{path}?{cb()}", name="MEDIA image",
                             catch_response=True, stream=False) as r:
            if r.status_code >= 500:
                r.failure(f"{r.status_code} server error")
            elif r.status_code == 429:
                r.failure("429 throttled")
            elif r.status_code >= 400:
                r.failure(f"{r.status_code}")
            else:
                r.success()


class ApiProbeUser(HttpUser):
    """Exactly one polite visitor, there to report what the API feels like.

    ~1 request/s: fast enough that a 20 s step yields ~20 samples (a p95 needs
    more than the handful a 3 s wait produced), slow enough to stay well under
    DEFAULT_THROTTLE_RATES['anon'] = 120/min. Do not speed this up — past 2 req/s
    the probe measures the throttle rather than the server.
    """
    fixed_count = 1
    wait_time = between(0.8, 1.2)

    def _probe(self, path, name):
        with self.client.get(f"{path}?{cb()}", name=name, catch_response=True) as r:
            if r.status_code == 429:
                r.failure("429 throttled")
            elif r.status_code >= 500:
                r.failure(f"{r.status_code} server error")
            else:
                r.success()

    @tag("media")
    @task(3)
    def stats(self):
        self._probe("/api/v1/stats/", name="PROBE API /stats")

    @tag("media")
    @task(2)
    def events(self):
        self._probe("/api/v1/events/", name="PROBE API /events")

    @tag("media")
    @task(1)
    def spa_shell(self):
        self._probe("/", name="PROBE SPA /")
