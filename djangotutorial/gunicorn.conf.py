"""Gunicorn config — RAM-conscious defaults for Render.

Start command (run from this directory, where manage.py lives):
    gunicorn mysite.wsgi -c gunicorn.conf.py

Env overrides:
    WEB_CONCURRENCY    number of worker processes (default 3)
    GUNICORN_THREADS   threads per worker          (default 2)
    PORT               bind port (Render sets this automatically)

So the service handles WEB_CONCURRENCY × GUNICORN_THREADS = 6 requests at once.
That number is the ceiling every load test runs into, and it is why serving media
through Django hurts: a 900 kB image holds one of those six slots for the whole
transfer.

## Why three workers fit where two used to be the limit

Worker count is bounded by the most expensive thing a worker can be doing, and
here that is decoding an uploaded image — a 24 MP PNG with an alpha channel
peaks at 286 MB of RSS, against a ~60 MB idle worker. Multiply that by the
worker count and even two barely fit in 512 MB:

    2 × 286 = 572 MB    over the instance, before serving a single page

What changed is that decoding is now serialised across the WHOLE instance by a
file lock (`leaderboard/image_utils.decode_slot`, IMAGE_DECODE_SLOTS=1), not
just within one process. Only one worker can be in that expensive state at a
time, so the budget becomes:

    1 × 286  +  2 × 60  = 406 MB     46 MB above the 60 MB safety margin

Measured, not estimated — `imagelab/07_memory.py` prints exactly this sum and
recomputes it for other instance sizes:

    INSTANCE_MB=1024 WEB_CONCURRENCY=6 /usr/bin/python3 imagelab/07_memory.py

## Before raising this further

Adding a worker costs one idle floor (~60 MB), which is cheap — 4 workers is
466 MB, still inside the instance but past the safety margin. The honest levers,
cheapest first:

  1. lower IMAGE_MAX_MEGAPIXELS (env, no deploy) — the peak scales with it
  2. a bigger instance
  3. raise IMAGE_DECODE_SLOTS only together with 2, since each extra slot adds a
     whole peak, not a floor

What does NOT work is raising this number and hoping: the failure mode is an OOM
kill during a burst of uploads, which takes down every request the worker was
serving and looks like a random outage rather than an upload problem.

## When the lock stops being the right answer

The decode lock is the cheap solution for "uploads are occasional". It holds a
gunicorn thread while it waits, so it trades throughput for memory, and that
trade is only good while waiting is rare.

The signal that it has stopped being good is 503s from the upload endpoints
becoming routine rather than exceptional (they are logged as
`Service Unavailable: /api/v1/photos/`). At that point the fix is not a tighter
lock or a longer wait — it is taking decoding out of the request cycle
altogether: the request stores the original and returns 202, and a background
worker (Celery on its own Render service, sized independently) does the decode.
That also decouples the two things this file currently has to balance in one
number: how many requests we serve, and how much RAM one upload may cost.

Not set here, but worth knowing about (set it in Render's env, not in code):

    MALLOC_TRIM_THRESHOLD_=100000

A glibc knob. By default glibc keeps freed memory in the process rather than
returning it to the OS, and Pillow's large short-lived buffers make that look
like a leak: RSS climbs, Render's memory graph creeps, nothing is actually
leaking. Setting the threshold to ~100 kB makes free() hand memory back much
more eagerly, so RSS tracks real usage.

It buys memory headroom, NOT throughput — expect the load-test numbers to be
unchanged, and a fraction more CPU spent on syscalls. `max_requests` below is
the other half of the same problem (recycle a worker before it bloats).
"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

workers = int(os.getenv("WEB_CONCURRENCY", 3))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "gthread"

# Explicit, though it happens to be gunicorn's default, because another timeout
# is measured against it: image_utils.IMAGE_DECODE_WAIT_SECONDS (5 s) is how
# long an upload waits for a decode slot, and that wait plus the decode itself
# must finish comfortably inside this. Otherwise the arbiter kills the worker
# mid-request — every other request it was serving dies with it, and the user
# gets a dead connection instead of the clean 503 the decode lock would have
# returned. Raise one and you have to look at the other.
timeout = int(os.getenv("GUNICORN_TIMEOUT", 30))

# Load the app once in the master, then fork — workers share memory
# copy-on-write, which lowers aggregate RSS.
preload_app = True

# Recycle workers periodically so slow memory creep (e.g. Pillow fragmentation)
# doesn't accumulate. Jitter staggers restarts so they don't all recycle at once.
max_requests = 500
max_requests_jitter = 50
