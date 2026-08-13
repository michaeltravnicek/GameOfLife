"""Gunicorn config — RAM-conscious defaults for Render.

Start command (run from this directory, where manage.py lives):
    gunicorn mysite.wsgi -c gunicorn.conf.py

Env overrides:
    WEB_CONCURRENCY    number of worker processes (default 2)
    GUNICORN_THREADS   threads per worker          (default 2)
    PORT               bind port (Render sets this automatically)

So the service handles WEB_CONCURRENCY × GUNICORN_THREADS = 4 requests at once.
That number is the ceiling every load test runs into, and it is why serving media
through Django hurts: a 900 kB image holds one of those four slots for the whole
transfer. Raising it costs RAM, which on a small Render instance is the scarce
resource — measure before turning it up.

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

workers = int(os.getenv("WEB_CONCURRENCY", 2))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "gthread"

# Load the app once in the master, then fork — workers share memory
# copy-on-write, which lowers aggregate RSS.
preload_app = True

# Recycle workers periodically so slow memory creep (e.g. Pillow fragmentation)
# doesn't accumulate. Jitter staggers restarts so they don't all recycle at once.
max_requests = 500
max_requests_jitter = 50
