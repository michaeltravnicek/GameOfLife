#!/usr/bin/env bash
#
# Render start command. Set the service's Start Command to:  bash start.sh
# (runs on every deploy AND every restart, unlike build.sh which runs only on
# deploy). Must live next to manage.py + gunicorn.conf.py.
set -o errexit
cd "$(dirname "$0")"

# No boot-time sheet sync: it spawned a second Django process (~66 MB) next to
# the starting workers on a 512 MB box, and build.sh plus the daily Render cron
# already sync. If stale data after a bare restart ever bites, re-enable with a
# delay so the spike misses worker startup:
# ( sleep 45; python manage.py sync_sheets || echo "start.sh: sync_sheets failed" ) &

# exec so gunicorn becomes PID 1 and receives Render's TERM/HUP signals directly.
exec gunicorn mysite.wsgi -c gunicorn.conf.py
