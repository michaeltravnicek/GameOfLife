# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**GameOfLive** — the leaderboard site for gameofyolo.com: events with point awards, RSVP,
feedback and geo check-in; all-time and per-season rankings with badges; user profiles with
enforced privacy flags; a photo gallery with likes; a daily Google Sheets sync of form responses.

**Architecture in one line:** a Django 5.2 + DRF API with a React 19 + Vite SPA, deployed as
one Render service — Django serves the built SPA via WhiteNoise. PostgreSQL on Render, Redis
cache, media on Cloudflare R2. [ARCHITECTURE.md](djangotutorial/ARCHITECTURE.md) records the
decisions; [security/RUNBOOK.md](security/RUNBOOK.md) holds the Cloudflare / Render / Google
console steps that cannot live in code.

## Layout

```
djangotutorial/               Django project — run manage.py from here
  mysite/                     settings.py, urls.py, views.py (SPA shell, healthz), og.py
                              (server-rendered OG tags), middleware.py (Cloudflare origin
                              lock, admin CSP exemption), drf.py (API error shape)
  leaderboard/                core app — API-only, no page views, no templates
    models.py                 Season, Category, Badge, Event, ImageToEvent, User (= player),
                              UserToEvent, UserBadge, EventRSVP, EventFeedback, UserPhoto…
    api/                      DRF views / serializers / urls, mounted at /api/v1/
    services/                 business logic (events, leaderboard, home, gallery, badges…)
    privacy.py                profile privacy flags — used by the API and by og.py
    checkin.py                geo check-in
    merging.py                soft, reversible merge of archive players into accounts
    image_utils.py            upload validation, WebP pipeline, host-wide decode slot
    cache_config.py           every cache key and TTL, and the invalidators
    tasks.py                  Google Sheets sync
    management/commands/      sync_sheets, ensure_season, generate_image_variants, …
    tests/
  accounts/                   auth + Profile (links auth.User to a leaderboard User)
    api/, services.py, adapters.py (Google login), matching.py (merge suggestions)
  gunicorn.conf.py, start.sh  Render start command and the memory budget behind it
frontend/                     the React SPA
  src/pages/                  one directory per route
  src/components/             shared UI
  src/services/               api.js (axios + CSRF), queryCache.js, errors.js
  src/context/AuthContext.jsx session user + role flags
  src/styles/                 design tokens and global CSS
  image-src/ → public/img/    `npm run images` writes WebP variants (public/img is gitignored)
build.sh                      Render build: npm build → stage SPA → collectstatic → migrate → sync
loadtest/                     Locust tooling and the R2 baseline
script/                       one-off import scripts — contain PII and a service-account
                              key; gitignored, do not commit or move
```

## Conventions that matter

- **Session cookies are the only credential.** Token auth was removed with the mobile app;
  do not reintroduce it. Plan features as web-session-only.
- **Registration creates the player** (`accounts.services.ensure_leaderboard_user`). An archive
  player with the same e-mail is adopted; anything less exact is an admin merge
  (`leaderboard/merging.py`) — soft and reversible via `User.merged_into`. `User.objects` hides
  merged rows; `User.all_objects` does not.
- **Privacy flags are enforced server-side** (`leaderboard/privacy.py`). Any endpoint that exposes
  profile data must honour them; so must `mysite/og.py`.
- **Write endpoints are transactional** — every POST/PUT/PATCH/DELETE runs under
  `transaction.atomic`.
- **Cache invalidation lives in model `save()`/`delete()`**; `cache_config.py` owns the keys.
  Writes that bypass `save()` (queryset `update()`, the sync) evict explicitly; bulk runs batch
  with `suspend_points_cache_invalidation()`.
- **Images:** every user upload goes through `validate_upload()`; models call
  `process_image_field()`, driven by `UPLOAD_LIMITS` / `ENFORCED_ASPECT` in `image_utils.py`
  (stored as WebP, per-field size caps, a mobile variant). Static images: `npm run images`.
- **Event creation lives in React** (`CreateEventPage` / `EditEventPage`). Django admin is for
  manual fix-ups only.
- **Account deletion anonymises** (`accounts.services.anonymize_account`): the account and its
  files go, the player row stays with a blank name so nobody's rank moves. The privacy policy
  (`PrivacyPage.jsx` §6) promises exactly this — change both or neither.
- **Google Forms are link-only.** The native renderer (`leaderboard/google_form.py`) is switched
  off by `settings.GOOGLE_FORM_NATIVE`; `EventRSVP` is the record of intent, the answers live in
  the spreadsheet.
- **UI copy is Czech.** API keys are snake_case as the server sends them.
- **Comments state intent or a constraint, never history.** Git holds the history.
- **Keep `npm run lint` at zero.** A scoped disable needs a reason; the react-hooks effect rules
  report on the `setState` inside the effect, so those need block disables.

## Routing

Routes are client-side (React Router, `frontend/src/App.jsx`). Django owns only the reserved
prefixes; everything else falls through to `index.html` with server-rendered OG tags — and a 404
status when the URL names content that does not exist.

SPA: `/` · `/events` · `/events/:slug` · `/events/vytvorit` · `/events/:slug/upravit` ·
`/galerie` · `/leaderboard` · `/historie` · `/o-bodech` · `/profil`, `/profil/:username` ·
`/upravit-profil` · `/hrac/:userId` · `/prihlasit` · `/registrace` · `/zapomenute-heslo` ·
`/obnova-hesla/:uid/:token` · `/ochrana-osobnich-udaju` · `/sprava/zpetna-vazba` (admin)

Django (`mysite/urls.py`): `/api/v1/` (leaderboard, `auth/`, `profiles/`) · `/accounts/`
(allauth) · `settings.ADMIN_URL` · `/media/`, `/static/`, `/sitemap.xml`, `/robots.txt`,
`/whoami/` · `/healthz/` (DB + cache probe — point Render's health check here) ·
`/api/schema/…` (DEBUG only). Unknown `/api/…` paths answer JSON.

## Working locally

Use the repo's virtualenv, `.venv/bin/python` — a bare `python3` lacks the project's packages.

```bash
pip install -r requirements.txt && (cd frontend && npm install)
docker compose up -d                                 # Postgres + Redis + adminer
cd djangotutorial && ../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver              # API on :8000
cd frontend && npm run dev                           # Vite on :5173; proxies /api, /media, /admin
```

Sheets sync: `manage.py sync_sheets` (skips if already synced today; `--force-all` to redo).
The daily run is a Render cron; the boot-time sync in `start.sh` is disabled for memory.

The admin is at `settings.ADMIN_URL` (env `ADMIN_URL`; production refuses the default `admin/`).

### Environment

`DJANGO_SECRET_KEY` (production refuses to boot without it) · `DATABASE_URL` · `MODE=PRODUCTION`
(`DEBUG = MODE != "PRODUCTION"`) · `ADMIN_URL` · `ALLOWED_HOSTS` · `CSRF_TRUSTED_ORIGIN` ·
`REDIS_URL` (in-process cache when unset) · `SENTRY_DSN` ·
`MEDIA_S3_BUCKET` / `ENDPOINT` / `ACCESS_KEY` / `SECRET_KEY` / `CUSTOM_DOMAIN` (R2;
`MEDIA_S3_ENABLED=0` keeps serving from disk during a cutover) · `WEB_CONCURRENCY`,
`GUNICORN_THREADS` (see `gunicorn.conf.py`). Frontend build-time vars in
`frontend/.env.production` are committed on purpose — they end up in the public bundle anyway.

## Tests

Both suites run in CI (`.github/workflows/tests.yml`).

```bash
cd djangotutorial   # in-memory SQLite, no Postgres needed
DJANGO_SETTINGS_MODULE=mysite.test_settings DJANGO_SECRET_KEY=x \
  ../.venv/bin/python manage.py test leaderboard accounts
cd frontend && npm run test:run && npm run lint
```

## Deployment

Render runs `build.sh` (deps → SPA build staged into `staticfiles/react/` → collectstatic →
migrate → `ensure_season` → sheet sync → image-variant backfill) and starts the service with
`bash start.sh` from `djangotutorial/` (gunicorn under `gunicorn.conf.py`, which documents the
memory budget — re-measure with `script/memory_budget.py` before changing worker counts).

## Design system

Tokens are CSS custom properties in `frontend/src/styles/colors_and_type.css`:
`--color-pink #e15463` (accent / CTA / hover), `--gol-purple #2a2468`, `--gol-dark #1a0f0a`,
`--gol-cream #fff1d4`, `--gol-gold #f5c842`. The homepage is the reference: hard cuts, opaque
cards; ticket skin on texture, poster card on photos, frost for chrome only, cream ticket for
events only.

## Open items

- Season rollover is not automated beyond `ensure_season` on deploy.
- `Sezóna 2025/26` is hard-coded in the four auth pages; they also duplicate their card shell
  (an `AuthShell` component is the pending extraction).
- `SERVICE_ACCOUNT_FILE` in `tasks.py` is a cwd-relative path, and the sync is not wrapped in
  a transaction.
- `loadtest/results/` holds the before-R2 run only; the after-R2 run was never recorded.

Before making any claim, label your confidence: [Certain] for information backed by strong evidence, [Likely] for conclusions based on solid reasoning, and [Guessing] when filling in missing information. If most of your response is based on guesses, say so upfront.
