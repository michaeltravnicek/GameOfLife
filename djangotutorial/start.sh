#!/usr/bin/env bash
#
# Render start command. Set the service's Start Command to:  bash start.sh
# (runs on every deploy AND every restart, unlike build.sh which runs only on
# deploy). Must live next to manage.py + gunicorn.conf.py.
set -o errexit
cd "$(dirname "$0")"

# Refresh leaderboard data from Google Sheets on boot.
#   * Backgrounded (&) so a slow sync never delays the port bind / health check.
#   * sync_sheets self-skips if it already synced today (see the LastUpdate guard
#     in the command), so repeated restarts within a day are effectively no-ops.
#     Add --force-all if you want every restart to do a full re-sync instead.
#   * Guarded (|| echo) so a sync failure — e.g. a missing credentials.json —
#     can never stop the web server from starting.
( python manage.py sync_sheets || echo "start.sh: sync_sheets failed, continuing" ) &

# exec so gunicorn becomes PID 1 and receives Render's TERM/HUP signals directly.
exec gunicorn mysite.wsgi -c gunicorn.conf.py
