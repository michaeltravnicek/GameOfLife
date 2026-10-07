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
  # Pre-compress the bundle (.gz/.br siblings WhiteNoise serves on Accept-Encoding).
  # collectstatic only post-processes files it collects through the finders, and
  # this directory is staged by hand above, so every chunk left the origin
  # uncompressed. The edge re-compresses for browsers, but each cache miss
  # still crossed origin -> Cloudflare at full size.
  python -m whitenoise.compress staticfiles/react
fi

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py ensure_season

# Folds same-person duplicate players into one (reversible merges, idempotent).
# A failure is logged, not fatal: duplicates are cosmetic, a failed deploy is not.
python manage.py dedupe_players --apply || echo "build.sh: dedupe_players failed, continuing"

# Backfill mobile WebP variants for media uploaded before the variant pipeline
# (idempotent — existing variants are skipped, so this is cheap on re-deploys).
python manage.py generate_image_variants

python superuser.py
