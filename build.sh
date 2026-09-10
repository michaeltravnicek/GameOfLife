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

python manage.py sync_sheets --force-all

# ---------------------------------------------------------------------------
# TEMPORARY — remove after one successful deploy.
#
# The R2 cutover flipped MEDIA_S3_ENABLED on before the existing files were
# copied, so every stored image URL now points at a bucket that only holds what
# has been uploaded since. This copies MEDIA_ROOT up under the SAME keys the
# database already stores, which is why no data migration is needed.
#
# It lives here because Render SSH needs a paid instance type, so there is no
# shell to run it from. Both calls are guarded: build.sh runs under `set -o
# errexit`, and a half-finished upload should not also cost a deploy -- the
# service would stay on the old build and the images would still be missing.
# Read the deploy log instead; --verify prints exactly what is still absent.
#
# Ordering matters: it must precede generate_image_variants. With S3 active that
# command reads through the storage backend, so the originals have to be in the
# bucket before it can find anything to make variants from. The filesystem walk
# also carries the existing .mobile.webp siblings up, so most variants arrive
# already made and the step below is a cheap no-op.
python manage.py migrate_media_to_s3 || echo "build.sh: migrate_media_to_s3 failed, continuing"
python manage.py migrate_media_to_s3 --verify || echo "build.sh: SOME MEDIA IS STILL MISSING FROM THE BUCKET (see above)"
# ---------------------------------------------------------------------------

# Backfill mobile WebP variants for media uploaded before the variant pipeline
# (idempotent — existing variants are skipped, so this is cheap on re-deploys).
python manage.py generate_image_variants

python superuser.py

# Register daily 4 AM Google Sheets sync cron job
# PROJECT_DIR="$(pwd)"
# PYTHON_BIN="$(which python3)"
# CRON_CMD="0 4 * * * cd $PROJECT_DIR && $PYTHON_BIN manage.py sync_sheets >> /tmp/sync_sheets.log 2>&1"
# ( crontab -l 2>/dev/null | grep -v "sync_sheets"; echo "$CRON_CMD" ) | crontab -
# echo "Cron job registered: daily sync at 4 AM"
