# Load testing

**Production runs live in [R2_BASELINE.md](R2_BASELINE.md)** — the measured
before/after around moving media to Cloudflare R2, plus the one command that
reproduces it. Everything below is the *local* setup.

Answers two questions with numbers instead of guesses:

1. How many concurrent visitors does the app handle before it degrades?
2. Is the limit the **API** or the **media files**?

Media is currently served by Django itself
([mysite/urls.py](../djangotutorial/mysite/urls.py) → `django.views.static.serve`),
which ties up a worker for the whole file transfer. If the media-only run
collapses far earlier than the API-only run, that's the case for moving images
to S3/R2 — measured, not assumed.

## Rules for a meaningful result

**Run gunicorn, never `manage.py runserver`.** The dev server's concurrency
model has nothing to do with production; numbers from it are worthless.

**Match production's worker count.** Whatever Render is set to. `WEB_CONCURRENCY`
in the local `.env` is `1` — if that's also what Render runs, that alone is a
finding.

**Load-generator and server on one machine share a CPU.** Locally you are
measuring a rough shape, not absolute capacity. Treat the *ratio* between the
API and media runs as the signal, not the raw requests/sec.

## Start the server

```bash
cd djangotutorial
DJANGO_SETTINGS_MODULE=mysite.settings_loadtest \
  /usr/bin/python3 -m gunicorn mysite.wsgi:application \
  --bind 127.0.0.1:8000 --workers 4 --access-logfile -
```

`settings_loadtest` disables the rate limiter, the axes lockout and Sentry —
otherwise you would be measuring the throttle, not the server. It is a separate
module (not an env-var switch) so it can never be turned on in production.

To check whether the *configured limits* are sane for real traffic, run the same
test against the normal `mysite.settings` and watch for `429 throttled`.

## Run the test

```bash
cd loadtest

# Web UI at http://localhost:8089
locust --host http://127.0.0.1:8000

# Headless, API only
locust --host http://127.0.0.1:8000 --tags api \
       --headless --users 100 --spawn-rate 10 --run-time 1m

# Headless, media only
locust --host http://127.0.0.1:8000 --tags media \
       --headless --users 100 --spawn-rate 10 --run-time 1m

# Both — what a real visitor does
locust --host http://127.0.0.1:8000 \
       --headless --users 100 --spawn-rate 10 --run-time 2m
```

## Reading the output

- **p95 response time** matters more than the average. The average hides the
  users having a bad time.
- **Failures** are split so they're readable: `429 throttled` is the rate
  limiter doing its job, `5xx server error` is the app breaking. Very different
  things.
- **RPS plateauing while response time climbs** = saturation. That's your
  ceiling.

Raise `--users` until p95 goes past ~1 s, and note the number. Do it for `api`
and `media` separately — the gap between them is the answer to question 2.
