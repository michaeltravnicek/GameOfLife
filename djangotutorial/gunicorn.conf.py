"""Gunicorn config — RAM-conscious defaults for Render.

Start command (run from this directory, where manage.py lives):
    gunicorn mysite.wsgi -c gunicorn.conf.py

Env overrides:
    WEB_CONCURRENCY    number of worker processes (default 2)
    GUNICORN_THREADS   threads per worker          (default 2)
    PORT               bind port (Render sets this automatically)
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
