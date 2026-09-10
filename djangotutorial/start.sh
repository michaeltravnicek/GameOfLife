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
# DISABLED 2026-09-10 — memory. This spawned a SECOND full Django process on the
# instance at boot, concurrently with gunicorn starting its workers: ~66 MB of
# imports (Django + google-api-python-client) before it even reads a sheet, on a
# 512 MB box that already budgets 3 x 60 MB for idle workers. It was also almost
# always a no-op on a deploy day, because build.sh has just run
# `sync_sheets --force-all` -- but the LastUpdate guard that skips the work sits
# INSIDE the command, so the import cost was paid regardless.
#
# What this loses: a re-sync on a restart that is not a deploy. The daily Render
# cron and build.sh both still sync. Re-enable if stale data after a bare restart
# ever actually bites; prefer `( sleep 45; ... ) &` so the spike does not land on
# top of worker startup.
# ( python manage.py sync_sheets || echo "start.sh: sync_sheets failed, continuing" ) &

# exec so gunicorn becomes PID 1 and receives Render's TERM/HUP signals directly.
exec gunicorn mysite.wsgi -c gunicorn.conf.py
