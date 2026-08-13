# Code Quality Audit — GameOfLive

Generated **2026-05-29**. Scope: **backend (Django/DRF API)** + **frontend (React SPA)** +
**config/deployment/production-readiness**. The `ClaudeDesign/` and `claudedesign/` mockup
folders are out of scope.

Severity: 🔴 high · 🟡 medium · ⚪ low. Each item has a file reference and a one-line fix.
Execution order lives in `~/.claude/plans/review-the-whole-codebase-tingly-porcupine.md`.

> This file replaces the 2026-05-02 audit, which only covered the old Django-template
> frontend that the React SPA has since replaced.

---

## Backend (Django / DRF)

### leaderboard/api/views.py

🔴 **RSVP capacity race (TOCTOU)** — [views.py:138-141](djangotutorial/leaderboard/api/views.py#L138-L141)
The `event.rsvps.count() >= event.capacity` check and `EventRSVP.objects.create(...)` run
inside `@transaction.atomic`, but the event row isn't locked, so two concurrent requests
both pass the count check and oversell capacity (READ COMMITTED won't see the other tx's
uncommitted insert). Fix: `Event.objects.select_for_update().get(...)` before counting.

🟡 **Weak event create/update validation** — `event_create` / `event_update`
`points` and `capacity` accept negative values; `checkin_radius` is unbounded; latitude/
longitude parse errors are silently swallowed (both set to `None` if either fails). Fix:
validate bounds explicitly and call `event.full_clean()` before `save()`.

🟡 **Feedback rating default is confusing** — [views.py:152-157](djangotutorial/leaderboard/api/views.py#L152-L157)
Defaults a missing rating to `0`, then rejects `< 1`. Reject "missing rating" explicitly
rather than routing it through the range check.

🟡 **Broad `except Exception` exposes internals** — `event_create` / `event_update`
`return Response({"error": str(exc)}, ...)` leaks internal error text to clients. Catch
specific exceptions; log the rest and return a generic message.

🟡 **Repeated ISO-datetime parsing** — `event_create` / `event_update`
The same ISO-string + timezone parsing block is duplicated ~4×. Extract to
`parse_iso_datetime()` in a new `leaderboard/utils.py`.

⚪ **Repeated `request.build_absolute_uri(field.url)`** across views + serializers.
Wrap in one `absolute_media_url(request, field)` helper.

### leaderboard/api/serializers.py

✅ **`EventListSerializer` category is not N+1** — `list_events`
([services/events.py:27](djangotutorial/leaderboard/services/events.py#L27)) already calls
`.select_related("category")`, so the nested `CategorySerializer` does not fan out. (An
earlier draft of this audit flagged this incorrectly.)

🟡 **`EventDetailSerializer` per-object query fan-out** — [serializers.py:93-137](djangotutorial/leaderboard/api/serializers.py#L93-L137)
`get_has_rsvp`, `get_has_attended`, `get_feedback_given`, `get_official_images`,
`get_user_photos` each issue their own query. This serializer is only used for **single**
objects (detail view + create/update responses), so it's ~5–7 queries per detail call — not
the list — but still worth trimming: pass the user's RSVP/feedback existence via context and
prefetch images/photos. (Not the "120+ on list" some scans claimed.)

⚪ **`from django.utils import timezone` imported inside `get_is_past`** (both serializers).
Move to module top.

### leaderboard checkin-events endpoint

🟡 **Two pre-existing failing tests** — `leaderboard.tests.test_home.CheckinEventsApiTests`
`test_anonymous_user_sees_no_active_events` and `test_user_without_profile_link_sees_nothing`
expect the `/api/checkin-events/` endpoint to return `[]` for anonymous users and users
without a linked `leaderboard_user`, but it currently returns the active event to everyone.
Either the endpoint should gate on auth + profile link (the tests' intent) or the tests are
stale. Verified these fail on `main` too — not introduced by this round of work.

### accounts/api/views.py

🟡 **No rate limiting on auth endpoints** — `login_api`, `register_api`, `password_reset_api`
have no throttling → brute-force and email-enumeration exposure. Add DRF throttles or
`django-ratelimit`. (Password reset already returns a generic message — good.)

### accounts/services.py & cross-app serialization

🟡 **Overlapping profile serialization** — `serialize_user()` / `profile_payload()` build
dicts that overlap with profile assembly in `leaderboard/api/views.py`. Consolidate into one
shared serializer/helper.

⚪ **Per-profile rank recomputation** — rank is computed by counting all higher-scoring
users on each profile view (O(n) per view). Cache it or derive from the cached leaderboard.

### leaderboard/tasks.py (Google Sheets sync)

🟡 **Sync not wrapped in a transaction** — `handle_attendance()` / `main()` create many
`UserToEvent` rows without `transaction.atomic`, so a mid-sync API failure leaves partial
state. Wrap each event's sync in a transaction.

⚪ **Hardcoded relative credentials path** — `SERVICE_ACCOUNT_FILE = '../credentials.json'`
is brittle; read the path from an env var with a sane default.

---

## Frontend (React)

### Duplicated logic (extract into `frontend/src/hooks/`)

🟡 **Form dirty-tracking + `beforeunload` guard** duplicated in `EditProfilePage`,
`CreateEventPage`, `EditEventPage`, `LoginPage`, `RegisterPage`. Extract `useForm()`.

🟡 **FileReader preview pattern** duplicated in `EditProfilePage` (avatar), `CreateEventPage`
(image+logo), `GalleryPage` (upload). Extract `useFilePreview()` and add a client-side
file-size check inside it.

🟡 **Inconsistent API error extraction** — pages unpack `err.response?.data` differently
(`.error` string vs `.errors` object). `services/errors.js` already has a `reportError`
helper; extend it to normalize both shapes and use it everywhere.

🟡 **Season-tab build + filter** duplicated in `EventsPage`, `LeaderboardPage`,
`GalleryPage`, `ProfilePage`. Extract `useSeasonTabs()`.

⚪ **Long page components** — `EventDetailPage.jsx` (~427 lines), `EditProfilePage.jsx`
(~382), `ProfilePage.jsx` (~350). Extract presentational sub-components so each reads
top-down.

### Bugs / robustness

🟡 **No Error Boundary** — any component throw blanks the whole SPA. Add one in
`App.jsx`/`main.jsx`.

🟡 **No 401 handling** — `services/api.js` has no response interceptor to redirect to login
on session expiry.

🟡 **Modal focus not trapped** — `components/Modal/Modal.jsx` sets `role="dialog"` +
`aria-modal` but keyboard focus can escape (A11y, WCAG 2.1 A).

⚪ **Logout error swallowed** — `context/AuthContext.jsx:50-59` ignores logout API failures
silently. Log it (client state still clears).

### Config

🟡 **Hardcoded API base URL** — `services/api.js:9` uses `baseURL: '/api'`. Use
`import.meta.env.VITE_API_URL || '/api'` so a split dev backend works; relative default
keeps prod unchanged.

⚪ **Missing client-side validation** — event `end_date ≥ start_date`, register password
strength. API rejects with cryptic errors today.

⚪ **Stubbed account actions** — `EditProfilePage.jsx` "pause/delete account" buttons are
`window.alert`/`confirm` placeholders. Wire up or hide.

---

## Config & Deployment

✅ **Secrets are NOT committed** — `git ls-files` confirms `credentials.json`,
`credentials1.json`, `djangotutorial/.env` are untracked; `.gitignore` covers
`credentials.json` and `.env`.
🟡 **Gap:** add `credentials1.json` to `.gitignore`; rotate the Google service-account key +
Django secret as a precaution since they sat in a working tree.

✅ **DEBUG correctly gated** — `DEBUG = MODE != "PRODUCTION"` ([settings.py:38](djangotutorial/mysite/settings.py#L38)).

✅ **Email / password reset configured** — [settings.py:210-222](djangotutorial/mysite/settings.py#L210-L222):
console backend in DEBUG, Gmail SMTP in prod.

✅ **build.sh references resolve** — `manage.py ensure_season` and `superuser.py` both exist.
⚪ `build.sh` uses `python` (not `python3`) and `superuser.py` runs via bare `python` — fine
on Render if `python` resolves to 3.x; worth pinning.

🟡 **`ALLOWED_HOSTS = ["*"]`** ([settings.py:39](djangotutorial/mysite/settings.py#L39)) —
fine for dev; set the real domain via env var in prod.

🟡 **No `CONN_MAX_AGE`** on `DATABASES` — connections aren't reused; add `CONN_MAX_AGE` (e.g.
600) for production.

🟡 **`SECRET_KEY` has an insecure hardcoded fallback** ([settings.py:25](djangotutorial/mysite/settings.py#L25)).
Acceptable as long as `DJANGO_SECRET_KEY` is always set in prod (Render does).

⚪ **CLAUDE.md is stale** — documents the old Django-template architecture/routes the React
SPA replaced. Refresh the structure + URL-routing sections.

---

## Production Readiness (must-do before launch)

🔴 **Media files on Render** — user uploads under `/media/` are served by a Django
`serve_media` view ([mysite/urls.py](djangotutorial/mysite/urls.py)). Render's default
filesystem is **ephemeral** — uploads vanish on redeploy. Use a Render persistent disk or
object storage (S3/Cloudinary). Biggest real production risk.

🔴 **Provision email env vars** — `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (Gmail app
password), `DEFAULT_FROM_EMAIL`. They default to `""`; password reset fails silently if
unset. Consider raising `ImproperlyConfigured` at startup in PROD.

🟡 **Set `MODE=PRODUCTION` + real `DJANGO_SECRET_KEY`** on Render; scope `ALLOWED_HOSTS`.

🟡 **Google Sheets sync cron is commented out** in `build.sh` — decide whether sync is still
needed in the React era; if yes, re-enable as a Render cron.

🟡 **Add auth rate limiting** (see backend section).

---

## Future Enhancements (good to add later)

- ⚪ Page-level React tests (only `queryCache`/`errors`/`ToastProvider` are covered today).
- ⚪ Error/log aggregation (Sentry) for SPA + Django.
- ⚪ CSS scope cleanup: unscoped `.row`/`.list`/`.empty` collisions across page CSS; consider
  CSS Modules. Standardize on `--color-*` tokens, retire `--gol-*` aliases.
- ⚪ Loading skeletons on season/tab switches (Leaderboard shows stale data while fetching).
- ⚪ RSVP/feedback optimistic UI with retry + undo toast.
- ⚪ Raise password `min_length` 4 → 8.
- ⚪ Audit logging for admin feedback access.

---

## Summary

| Area | 🔴 | 🟡 | ⚪ |
|------|----|----|----|
| Backend | 1 | 7 | 4 |
| Frontend | 0 | 7 | 4 |
| Config & Deployment | 0 | 4 | 3 |
| Production Readiness | 2 | 3 | 0 |
