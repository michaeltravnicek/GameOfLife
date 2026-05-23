#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Build the React frontend
if [ -d "frontend" ]; then
  pushd frontend > /dev/null
  npm ci
  npm run build
  popd > /dev/null
fi

cd djangotutorial

# Stage the React build under STATIC_ROOT/react/ so collectstatic + WhiteNoise can serve it.
mkdir -p staticfiles/react
if [ -d "../frontend/dist" ]; then
  cp -r ../frontend/dist/* staticfiles/react/
fi

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py ensure_season

python superuser.py

# Register daily 4 AM Google Sheets sync cron job
# PROJECT_DIR="$(pwd)"
# PYTHON_BIN="$(which python3)"
# CRON_CMD="0 4 * * * cd $PROJECT_DIR && $PYTHON_BIN manage.py sync_sheets >> /tmp/sync_sheets.log 2>&1"
# ( crontab -l 2>/dev/null | grep -v "sync_sheets"; echo "$CRON_CMD" ) | crontab -
# echo "Cron job registered: daily sync at 4 AM"
