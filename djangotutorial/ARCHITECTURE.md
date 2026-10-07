# Architecture Decisions

This document records key architectural choices for the GameOfLive project, including the reasoning and the conditions under which they should be revisited.

---

## Frontend: React SPA — decided 2026-05-01, **reversed and migrated**

### Decision (current)
The frontend is a **React + Vite single-page app** in `frontend/`, consuming the DRF API.
Django is **API-only**: it has no `views.py` for pages and no page templates. The only
templates left are `accounts/templates/` (password-reset mail + two Django-admin overrides).

The earlier decision — "Django templates now, React later" — was reversed when the migration
actually happened. It's recorded below for context, not as guidance.

### How it's wired
- **Build**: `build.sh` runs `npm ci && npm run build` in `frontend/`, copies `frontend/dist/*`
  into `djangotutorial/staticfiles/react/`, then runs `collectstatic`.
- **Serving**: one Render service. WhiteNoise serves the SPA from `WHITENOISE_ROOT =
  staticfiles/react`; `mysite/views.py` falls back to `index.html` so client-side routes
  deep-link correctly.
- **SEO**: crawlers don't run JS, so `mysite/og.py` renders server-side Open Graph tags for
  event/player/profile URLs (consent-gated — see `leaderboard/privacy.py`).
- **Auth**: session cookies only. Token auth was removed with the mobile app.

### What the earlier "prepare for React" work bought
The preparation paid off — the migration needed no API rewrite:
1. **DRF everywhere** — endpoints were already serializer-based, so React consumed them as-is.
2. **CSS design tokens** — custom properties carried over into the React styles directly.
3. **API-first data** — no server-rendered-only pages had to be reverse-engineered.

### Mobile app: cancelled 2026-07-26
A Capacitor wrapper (iOS + Android) was built and then abandoned. All of it — `frontend/android/`,
`frontend/ios/`, the `@capacitor/*` dependencies, the native shims (`platform.js`, `NativeBridge`,
`authToken.js`) and the unsigned-iOS CI workflow — was removed on 2026-07-27. Plan features as
**web-session-only**: no token auth, no extra CORS origins. If a native client is ever revived,
its credential should be short-lived and refreshable, not a permanent DRF token.

---

## Database: Render PostgreSQL (not Supabase) — decided 2026-05-01

### Decision
Stay on Render's managed PostgreSQL. Supabase evaluated and rejected.

### Why not Supabase
- **No meaningful gain at this scale**: Render PostgreSQL is equivalent to Supabase PostgreSQL for hundreds of users and <1 GB data.
- **Migration cost**: Django's ORM, auth, and admin work perfectly. Migrating to Supabase auth and storage would require rewriting large parts of the app.
- **Supabase free tier limits are tighter**: 500 MB DB, 1 GB storage, 2 projects vs. Render's paid plan.

### When to revisit Supabase
- If Render's DB pricing becomes a concern at scale
- If real-time subscriptions (live leaderboard) become a priority — Supabase has first-class WebSocket support
- ~~If file storage needs a CDN~~ — resolved: media moved to Cloudflare R2 (2026-09)

---

## Hosting: Render (current)

### Single Django service handles:
- Web server (Gunicorn)
- Static files (WhiteNoise)
- Media files: uploads go to Cloudflare R2 (`storages` S3 backend, served from
  `img.gameofyolo.com`); the `/media/` route remains for a cutover with `MEDIA_S3_ENABLED=0`

### RAM usage
Measured, not estimated — see `gunicorn.conf.py`: an idle worker is ~60 MB, ~100 MB once boto3
is loaded for R2, and one image decode peaks at 286 MB. Decodes are serialised across the
instance by a file lock, so the budget is `(workers − 1) × idle + peak`; on a 512 MB instance
that means two workers after R2. `script/memory_budget.py` recomputes the table.

### Why the React SPA did NOT need a second service
The SPA is a static bundle, not an SSR app, so WhiteNoise serves it from the existing Django
service — no Node process in production, no extra RAM, no second deploy target. This is the
main reason Vite/React was chosen over Next.js.
