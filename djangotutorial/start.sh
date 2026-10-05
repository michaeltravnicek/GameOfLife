#!/usr/bin/env bash
#
# Render start command. Set the service's Start Command to:  bash start.sh
# (runs on every deploy AND every restart, unlike build.sh which runs only on
# deploy). Must live next to manage.py + gunicorn.conf.py.
set -o errexit
cd "$(dirname "$0")"

# exec so gunicorn becomes PID 1 and receives Render's TERM/HUP signals directly.
exec gunicorn mysite.wsgi -c gunicorn.conf.py
