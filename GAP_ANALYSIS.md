# GameOfLive — gap analysis, and the work that follows from it

> *Audit run 2026-08-11 against branch `feature/google-form-native-signup`; **all nine items were
> implemented on 2026-08-12** — see the table at the bottom. This is the working
> plan — tick items off in the "Suggested order" table at the bottom as they land. The two dated
> snapshots it refers to (`CODE_REVIEW.md`, `TESTING_REPORT.md`) are from 2026-07-03 and are
> superseded by this document wherever they disagree.*

## Context

I audited the project for what's *missing*: git/remote state, both test suites, the production
build, dependency advisories, runtime wiring (settings → modules), data model vs. shipped UI,
GDPR promises vs. code, SEO/a11y, ops, doc accuracy.

**Health where it counts is good.** Backend **556 tests green**, frontend **72 green**, build clean
(279 kB main / 90 kB gz, Leaflet isolated), zero `TODO`/`FIXME` in app code. Privacy flags *are*
enforced, login no longer leaks usernames, and both 🔴 "rewrite candidates" from `CODE_REVIEW.md`
(EventForm extraction, `EventWriteSerializer`) are **done**. The gaps are mostly *around* the code.

You reviewed the findings and directed the work: e-mail verification is **not a problem** and season
rollover is **deferred** (both noted at the end); photo likes and profile questions get **built**;
the dependency advisories needed explaining; **Google Forms goes back to link-only** — the native
rendering from commit `7d1ba78` is switched off behind a flag and the sign-up page is removed, with
the form link returning to the RSVP modal where it used to live; and the remaining findings move
from a backlog into the plan proper (Parts 5–6).

---

# Part 1 — Blocking: a fresh clone does not run

Tracked code imports files that were never `git add`-ed. Render builds from a clean clone, so this
is not cosmetic.

| Untracked file | Who needs it | Failure on a clean clone |
|---|---|---|
| `djangotutorial/accounts/axes_handler.py` | `settings.py:432` `AXES_HANDLER` | django-axes resolves the handler at app init → **Django won't start** |
| `djangotutorial/leaderboard/merging.py` | `accounts/services.py:68`, `leaderboard/tasks.py:74` | `ImportError` on registration and on every sheet sync |
| `leaderboard/migrations/0026_…`, `0027_user_soft_merge.py` | tracked `models.py` (`merged_into`, `merged_at`, no `phone_number`) | `migrate` leaves the DB behind the models |
| `frontend/src/pages/NotFound/*` | tracked `App.jsx:28` | **Vite build fails** — unresolved import |
| `.github/workflows/tests.yml` | GitHub Actions | workflows only run if they exist on the remote → **CI has never run** |
| `accounts/management/commands/backfill_player_accounts.py`, `leaderboard/.../export_player_numbers.py` | the identity-pivot runbook | commands missing when you need them |
| 6 test modules (`test_merging`, `test_account_lockout`, `test_cache_invalidation`, `test_throttle_config`, `accounts/test_player_creation`, `hiddenSections.test.jsx`) | — | the suites proving the newest work vanish |

Also: **`main` is `3692576` from 2026-04-22** (pre-React). All current work lives on
`origin/alternative2` plus **1 unpushed commit** (`7d1ba78`) and **56 modified files**. `main` does
not describe the live product, and those 56 files exist only on this laptop.

**Do first:** `git add` the above → commit → push → merge to `main` under a real branch name.
Keep `GOL_Web_Manual_2026.pdf` (86 MB, untracked and un-ignored in the root) *out* — add it to
`.gitignore` before any `git add -A`.

---

# Part 2 — The dependency advisories, explained

You asked to understand these. `npm audit --omit=dev` reports 4 (3 high). **Two of the three highs
do not apply to this app. One does, and it is live in your login flow.**

### ❌ `form-data` 4.0.5 — not applicable
CRLF injection via multipart field names (CVSS 7.5). `form-data` is a **Node-only** transitive dep
of axios's HTTP adapter. I grepped the built bundle: it contains the string `"multipart/form-data"`
(a content-type header) but **not the package**. Browsers use native `FormData`. Not reachable.

### ❌ `axios` 1.16.0 — not applicable
Its one *high* is "Node HTTP adapter can use an inherited proxy after interceptor config cloning" —
**Node adapter only**; the browser build uses XHR/fetch. The moderates are `maxBodyLength` bypasses
(Node), `NO_PROXY` handling (Node), and prototype-pollution gadgets that need attacker-controlled
config objects — `api.js` builds every config itself. Not reachable.

### ✅ `react-router` 7.15.0 — **one advisory genuinely applies**

Four of the six are RSC / SSR-hydration / framework-mode issues. This is a `BrowserRouter` Vite SPA
with no SSR and no RSC — not applicable. The "Unauthenticated DoS via Inefficient Route Matching"
high concerns a *server* doing the matching; here matching happens in the visitor's own browser.

The one that does apply is **[GHSA-wrjc-x8rr-h8h6 — open redirect via backslash in `<Link>` /
`useNavigate`](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6)**.

#### You already know this bug — it's Django's `?next=`

Django's `LoginView` accepts `?next=/some/page/` and sends you there after login. If Django just
trusted that value, `?next=https://evil.com` would bounce your user off-site right after they typed
their password. That's why Django ships
[`url_has_allowed_host_and_scheme()`](https://docs.djangoproject.com/en/5.2/ref/utils/#django.utils.http.url_has_allowed_host_and_scheme)
and `LoginView` calls it on every `next` before redirecting.

Your React login does the same thing, with the same parameter, **minus the check**:

```jsx
// LoginPage.jsx:30 — and RegisterPage.jsx:72, identical
const from = location.state?.from || searchParams.get('from');   // ← from the URL
navigate(from || `/profil/${u.username}`, { replace: true });    // ← used unchecked
```

`searchParams.get('from')` is just "read `?from=` out of the address bar" — the React equivalent of
`request.GET.get("next")`. `navigate(...)` is "go to this path" — the equivalent of
`redirect(...)`. Nothing between them validates the value. **There is no React Router equivalent of
`url_has_allowed_host_and_scheme()`; you have to write it yourself.**

#### Why the backslash matters

`navigate()` is *supposed* to only accept in-app paths like `/profil/honza`. If someone passes
`//evil.com`, React Router recognises that as "not a path" and refuses. The bug is that
**`\/\/evil.com` (with backslashes) slips past that check** — React Router reads it as an ordinary
path, hands it to the browser, and the browser treats `\` and `/` as the same character in a URL.
So it becomes `//evil.com`, which means "go to evil.com".

The attack in three steps:

1. A member gets a link to **your real site**: `https://www.gameofyolo.com/prihlasit?from=\/\/evil.com`
   — real domain, real padlock, real login form. Nothing looks wrong.
2. They log in. It genuinely works.
3. `navigate()` sends them to `evil.com`, which shows a copy of your login page saying "session
   expired, log in again" — and this time it keeps the password.

#### Verify it yourself (2 minutes, no tooling)

```
npm run dev
open  http://localhost:5173/prihlasit?from=\/\/example.com
log in
```
If the address bar ends up on `example.com`, it's real. After the fix it must stay on `localhost`.
Try `?from=/leaderboard` too — that one **must still work**, or you've broken the normal redirect.

#### The fix — two halves, both worth doing

- **Upgrade** `react-router-dom` to ≥ 7.15.1 — a patch release on the same major version, so no API
  changes. `npm audit fix` does it. Bump axios/form-data in the same pass; free even if unreachable.
- **Validate `from` yourself** — this is the half that lasts, because it's correct no matter which
  router version you're on. It's a five-line `url_has_allowed_host_and_scheme()` for the frontend,
  living next to `frontend/src/utils/shareUrl.js`:

  ```js
  // Accept only in-app paths: one leading slash, no backslashes.
  // Rejects //evil.com, \/\/evil.com, https://evil.com, javascript:...
  export const safeRedirect = (to, fallback) =>
    (typeof to === 'string' && /^\/(?!\/)/.test(to) && !to.includes('\\')) ? to : fallback;
  ```

  Then both call sites become `navigate(safeRedirect(from, '/profil/' + u.username), …)`.
  Unit-test it next to `shareUrl`'s tests — pure function, no React involved, so the test is a
  handful of `expect(safeRedirect(x, '/fallback'))` lines.

---

# Part 3 — Finish the two half-built features

## 3a. Photo likes ("Add")

Today: `PhotoLike` model + `PUT/DELETE /api/v1/photos/<id>/like/` + `setPhotoLike()` in `api.js`
all exist with **zero callers**, and the gallery payload emits no photo `id` and no like state — so
a button could not render. Three layers, none connected.

Scope note: likes hang off `UserPhoto`. The gallery merges those with official `ImageToEvent` rows,
which have no like model. **Keep it that way** — likes on community photos only; official event
photos simply don't show the control. Extending `PhotoLike` to `ImageToEvent` means a generic
relation and is not worth it.

**Backend** — `leaderboard/services/gallery.py`, `gallery_page()`:
- Add `"id": up.pk` to the user-photo dicts (official rows keep `"id": None`).
- Annotate the `user_photos` queryset with `Count("likes")` → `like_count`.
- **Avoid N+1 on `liked_by_me`**: don't query per photo. After slicing, do one
  `PhotoLike.objects.filter(auth_user=request.user, photo_id__in=ids).values_list("photo_id")`
  into a set, and map. Anonymous → `liked_by_me: False` for all.
- Official photos get `like_count: null` so the client can distinguish "not likeable" from "0 likes".

**Frontend** — `GalleryPage.jsx` + `Lightbox.jsx`:
- Heart button on user-photo tiles and in the lightbox info bar, hidden when `p.id == null`.
- **Optimistic update** with rollback on failure (the endpoint is idempotent PUT/DELETE, so a
  retried click is safe) — follow the RSVP pattern in `EventDetailPage.jsx`.
- Anonymous visitors: show the count, and route a click to `/prihlasit?from=/galerie`
  (through `safeRedirect` from Part 2).
- `aria-pressed` on the button, `aria-label` "Líbí se mi".

**Tests:** backend — like/unlike idempotency and that `like_count`/`liked_by_me` appear correctly
for anon vs. owner vs. other user; frontend — optimistic toggle and rollback.

## 3b. Profile questions ("add it in the edit profile")

Today: `ProfileQuestion` (text, order) and `ProfileAnswer` (auth_user, question, answer,
`unique_together`) exist with a Django-admin registration and **nothing else** — no serializer,
no endpoint, no UI. You author the questions in admin; members answer them on their profile.

**Backend:**
- `GET /api/v1/profile-questions/` — the ordered question list (`id`, `text`). Cacheable, changes rarely.
- Extend `update_profile()` in `accounts/services.py:360` to accept `answers` as
  `{question_id: text}` and `update_or_create` each `ProfileAnswer`. Empty string ⇒ delete the row,
  so "cleared" and "never answered" stay the same thing. Ignore unknown question ids rather than
  erroring — a stale open tab must not fail the whole save. Already inside the view's
  `transaction.atomic`, which matches the project rule on transactional writes.
- Expose answered pairs in `profile_payload()` (`accounts/services.py:205`) as
  `[{question, answer}]`, questions with no answer omitted.
- **Gate on privacy:** these are free-text self-descriptions. Fold them into the existing
  `visibility_for()` gates — a `members_only` profile must not leak them to anonymous viewers or to
  `mysite/og.py` link previews. Cap each answer server-side (e.g. 500 chars).

**Frontend** — `EditProfilePage.jsx`, new `<section className="gol-section">` between
"Co o sobě povíš" (bio) and "V čem jedeš" (categories), following the established
`gol-sec-heading` + `ep-sec-sub` pattern; one textarea per question with a character counter, wired
through the existing `markDirty()`. Display them in `ProfilePage.jsx` in the "O mně" area.

**Note:** with zero `ProfileQuestion` rows the section renders nothing — so ship a few starter
questions via a data migration or just add them in admin after deploy, otherwise the feature is
invisible and looks broken.

---

# Part 4 — Google Forms: back to link-only

**Decision: stop rendering Google Forms natively. Link out to Google, and put that link back in
the RSVP flow exactly as it worked before commit `7d1ba78`.** The native path stays in the repo,
switched off by a setting.

This also settles the "nothing is recorded locally" gap I raised — it disappears with the feature.
Once we only hand out a link, we *cannot* know who filled the form; that lives in the spreadsheet.
`EventRSVP` becomes the record of intent, which is what the old modal already did: it saves the
RSVP first, then "Zrušit účast" takes it back. No new model, no second PII store.

## 4a. Backend — keep it, flag it off

`settings.py`: `GOOGLE_FORM_NATIVE = os.getenv("GOOGLE_FORM_NATIVE", "") == "1"` (default **off**).

`event_signup_form` (`api/views.py:761`) returns the existing `{"embed_only": True, "url": …}`
shape immediately when the flag is off — that response already exists as the parse-failure path, so
no new contract. `event_signup_form_submit` returns **410 Gone** when off, rather than silently
accepting answers it won't forward.

Everything else stays untouched and tested: `leaderboard/google_form.py` (208 lines),
`tests/test_google_form.py` (257 lines), the fixture, both URL entries, the CSP `frame-src` for
`docs.google.com`/`forms.gle`. `requirements.txt` keeps `requests` — `google_form.py` still imports
it, and it arrives via allauth regardless.

**Be honest about what the flag restores.** Flipping it back on revives the *backend*. The
frontend page is deleted below, so a full revival is: flip the flag **and** restore
`frontend/src/pages/EventSignup/` + its route from commit `7d1ba78`. Say exactly that in the
comment next to the setting, with the hash — otherwise the flag reads as a promise it can't keep.

## 4b. Frontend — delete the page, restore the modal

**Delete** the `/events/:slug/prihlaska` route (`App.jsx:15,77`) and
`frontend/src/pages/EventSignup/` — `EventSignupPage.jsx` (322 lines), its CSS, `FormFields.jsx`
+ test. Recoverable from `7d1ba78`.

**Keep `embedUrl.js` — move it, don't delete it.** `toFormUrls()` rewrites the `/edit` URL admins
actually paste into a working `/viewform` one and strips the author's `ouid`. That matters *more*
in link-only mode, because now the raw URL is the only thing the member gets. Move
`embedUrl.js` + `embedUrl.test.js` to `frontend/src/utils/`, and use `toFormUrls(url)?.link ?? url`
for the href. The `.embed` half stays for the flag's sake.

**Restore the survey modal** in `EventDetailPage.jsx` from `7d1ba78^` — it's a clean revert of that
file's hunks:

- `const [surveyOpen, setSurveyOpen] = useState(false)`
- in the RSVP handler, replace `navigate(\`/events/${slug}/prihlaska\`)` with `setSurveyOpen(true)`
- restore `handleSurveyDone` (closes, keeps the RSVP) and `handleSurveyCancel` (closes, calls
  `setRsvp(slug, false)`, invalidates `events:` cache, refetches)
- restore the `<Modal>` block: eyebrow "— Ještě jedna věc —", a heading that differs for
  survey-vs-WhatsApp-only, the "Otevřít formulář ↗" / "Přidat se do WhatsApp skupiny ↗" links
  (`target="_blank" rel="noopener noreferrer"`), and the `Zrušit účast` / `Hotovo` buttons
- restore the `.survey-modal-*` rules in `EventDetailPage.css`
- remove the `Button as="link" to={…/prihlaska}` at `EventDetailPage.jsx:451`; if you still want a
  way back to the form after joining, make it a plain `<a>` to the same sanitised URL

Check `EventFormSections.jsx` (7 lines changed in that commit) — if the admin-facing hint tells
you to paste a `/viewform` URL, it stays accurate and correct either way.

**Tests:** `FormFields.test.jsx` (10 tests) goes with the component. `embedUrl.test.js` (70 lines)
moves and must stay green — it's the one piece still on the live path. Add one
`test_google_form`-side case asserting `embed_only: True` when the flag is off. Frontend total goes
72 → ~62; that's expected, not a regression.

---

# Part 5 — Account deletion, so the privacy policy is true

`PrivacyPage.jsx` §6 promises, in writing: we delete your name, nickname, e-mail, photo, bio and
social links; points and attendance stay **anonymised**. Today there is no endpoint, no UI and no
command — only Django admin. A published promise you can't execute is the exposure, so this is the
largest item in the backlog and the one worth doing properly.

**`DELETE /api/v1/auth/me/`** (session auth, `transaction.atomic`), plus an
`anonymize_account <username>` management command sharing the same service function so you can run
it by hand for an e-mailed request.

What it does, matching the policy sentence by sentence:

| Row | Action | Why |
|---|---|---|
| `auth.User` | delete | the account itself |
| `accounts.Profile` | cascades — photo file deleted from storage too | photo, bio, city, socials |
| `leaderboard.User` (the player) | **keep, anonymise**: `name` → `""`, `email` → `None` | `short_name()` already renders an empty name as **"Hráč"**, so the leaderboard stays intact with no code change |
| `UserToEvent` | keep untouched | the points the policy says are retained |
| `EventFeedback` | keep `rating`, blank `comment` | ratings are aggregate; free-text may contain things about themselves |
| `UserPhoto`, `PhotoLike`, `EventRSVP` | cascade with `auth.User` | gallery photos are consent-based and consent is being withdrawn |

Two things to get right: **don't reuse the soft-merge** (`merged_into`) — merging hides a player
and moves their points; anonymising keeps them exactly where they are. And the anonymised player
must not be re-adoptable: `ensure_leaderboard_user()` matches on e-mail, and `email → None` is what
stops a later registration inheriting the row.

**UI:** a destructive-action section at the bottom of `EditProfilePage.jsx`, behind a `Modal`
confirmation that requires typing the username (the pattern the attendance remove-button already
sets), then logout + redirect home. State plainly in the dialog that points remain anonymised —
that's the surprising half.

**Not doing: data export/portability.** The policy mentions the right, but it's satisfiable by hand
on request at this scale. Revisit if requests ever actually arrive.

---

# Part 6 — The rest of the findings

Each is small and independent; do them in any order.

**Correctness**
- **Gate RSVP on past events** — `event_rsvp` (`api/views.py`) has no date check, so the API
  accepts an RSVP to a finished event and inflates the public "X účastníků". Open since
  `TESTING_REPORT.md` 2026-07-03. One guard returning 400, plus a test. Allow `DELETE` regardless,
  so someone can always leave.
- **Logged-in password change** — `POST /api/v1/auth/password-change/` (old password + new,
  `validate_password`, `update_session_auth_hash` so they stay logged in), and a section in
  `EditProfilePage.jsx`. Today the only route is logging out and mailing yourself a token.
- **API 404s return HTML** — unknown `/api/…` paths fall to Django's HTML 404, so a mistyped
  endpoint makes the SPA parse HTML as JSON. Add a JSON `handler404` scoped to the `/api/` prefix.

**Ops**
- **`/healthz/`** — Render's health check currently hits `/`, a memoised file read that returns 200
  with the database down. A view that does one trivial DB query plus a cache round-trip and returns
  `{"ok": true}`, `no-store`, no auth, excluded from the SPA catch-all's `_reserved` list.
- **Backup/restore procedure** — write it into `security/RUNBOOK.md`: what Render retains, how long,
  the exact restore steps, and whether R2 media has versioning. Untested backups aren't backups;
  the doc should end with "restore into a scratch DB once and confirm".
- **`uvicorn`** in `requirements.txt` is unused — the app runs gunicorn/WSGI. Drop it.

**Frontend polish**
- **Lint to zero** — 29 problems (20 errors, 9 warnings). CI runs `npm run lint`, so this goes red
  the moment Part 1 lands. Start with the genuine `no-unused-vars` (`queryCache.test.js:2`, stray
  `act` import); triage the `set-state-in-effect` errors — two are derived state that should be
  computed during render, the rest are legitimate synchronisation and can take a scoped disable
  with a reason.
- **PWA basics** in `frontend/index.html` — web manifest, `apple-touch-icon`, `theme-color`. It's a
  mobile-first community site people add to their home screen; today they get a blank icon.
- **Focus indicators** — 9 `outline:none` vs 6 `:focus-visible`. `.ep-combo .gol-input:focus`
  (`EditProfilePage.css:47`) strips focus with no replacement; the rest swap in a border colour,
  which is thin for WCAG 1.4.11. One shared `:focus-visible` token applied across the inputs.

**Documentation** — the live docs contradict the code *and each other*:

| File | Says | Actually |
|---|---|---|
| `CLAUDE.md` | 530 backend / 37 frontend tests | **556 / 72** (and ~62 frontend after Part 4) |
| `BACKEND_MAP.md` | "465 testů" (l.6), "454" (l.265), "459" (l.278); `settings.py` 836 | **556**; **875** |
| `FRONTEND_TODO.md` | privacy flags unenforced, `hide_pts` missing from UI | both **false** — `privacy.py`, `EditProfilePage.jsx:341` |
| `FRONTEND_TODO.md` | attendance UI at `/sprava/akce/<slug>/ucast` | lives **inside `EventDetailPage.jsx`**; that route doesn't exist |
| `CODE_REVIEW.md` | two 🔴 rewrites outstanding | **both done** |

Fix the three live docs (`CLAUDE.md`, `BACKEND_MAP.md`, `FRONTEND_TODO.md`) and add the routing
change from Part 4. Mark `CODE_REVIEW.md` and `TESTING_REPORT.md` as dated snapshots with a header
line rather than editing them — they're a record of a moment.

---

# Deferred by you

**Season rollover.** `ensure_season` runs only in `build.sh`, so with no deploy near 1 January the
old season stays active. When you pick it up, the cheapest fix is calling it at the start of
`sync_sheets` — that inherits both the daily cron and boot-time execution without touching the
Render dashboard. Related and already wrong today: four auth pages hardcode `Sezóna 2025/26`
(`LoginPage.jsx:46`, `RegisterPage.jsx:97`, `ForgotPasswordPage.jsx:48`, `ResetPasswordPage.jsx:56`)
while `Hero.jsx:54` says `Sezóna 2026` and the DB season is calendar-year.

**E-mail verification** — you called this not a problem; noting only that
`accounts/services.py:64`'s own docstring describes the consequence, so if you ever want the
docstring to stop saying that, this is the fix.

---

# Needs you, not me

Two items I've deliberately left out of the task list, because they aren't mine to execute:

- **`security/RUNBOOK.md`'s final checklist — all 13 boxes unchecked**, incl. Cloudflare Access on
  the admin path, `--verify` before `MEDIA_S3_ENABLED=1`, `CSP_ENFORCE=1`, and raising
  `SECURE_HSTS_SECONDS` from the 300 s ramp to a year. These are Cloudflare/Render/Google Cloud
  dashboard steps. Either they're done and the file is stale, or they're genuinely open — worth
  going through once and ticking, because right now the file can't tell you which.
- **Repo bloat** — `frontend/image-src/` is 139 MB of tracked 6–10 MB JPEGs; `.git` is 288 MB.
  Fixing it properly means rewriting history (`git filter-repo`) and force-pushing, which breaks
  every existing clone. **Say the word and I'll plan it separately**; I won't touch history
  otherwise. The cheap mitigation meanwhile: keep the 86 MB `GOL_Web_Manual_2026.pdf` gitignored
  so it never joins them.

---

# Suggested order

| # | Task | Size | Done |
|---|---|---|---|
| 0 | Save this plan as `GAP_ANALYSIS.md` in the repo root | 1 min | ✅ |
| 1 | `git add` untracked runtime files + CI workflow + the four root docs; `.gitignore` the 86 MB PDF; commit, push, merge to `main` | 30 min | ✅ (branch pushed; `main` merge deferred) |
| 2 | `safeRedirect()` helper + both call sites + test; `npm audit fix`; re-run suites | 1 h | ✅ |
| 3 | Photo likes end-to-end (payload + N+1-safe like state + UI + tests) | ½ day | ✅ |
| 4 | Profile questions (endpoint + `update_profile` + edit UI + profile display + privacy gate) | ½ day | ✅ |
| 5 | Google Forms → link-only: flag off, delete the page, restore the RSVP modal, move `embedUrl.js` | ~2 h | ✅ |
| 6 | Account deletion + anonymisation (endpoint, command, confirm-modal UI) — Part 5 | ½ day | ✅ |
| 7 | RSVP past-event gate · password change · JSON API 404 · `/healthz/` · drop `uvicorn` | ½ day | ✅ |
| 8 | Lint to zero · PWA manifest · `:focus-visible` pass | ~2 h | ✅ |
| 9 | Docs: fix the three live ones, header-stamp the two snapshots, write the backup procedure | ~2 h | ✅ |

## Verification

```bash
# 1 — prove a clean checkout works (this is the blocking one)
git clone . /tmp/gol-clean && cd /tmp/gol-clean
DJANGO_SETTINGS_MODULE=mysite.test_settings DJANGO_SECRET_KEY=x \
  /usr/bin/python3 djangotutorial/manage.py check   # must not ImportError on axes_handler
cd frontend && npm ci && npm run build              # must not fail on ./pages/NotFound

# 2 — open redirect, by hand. npm run dev, then log in via each URL:
#     http://localhost:5173/prihlasit?from=\/\/example.com  → must STAY on localhost
#     http://localhost:5173/prihlasit?from=/leaderboard     → must STILL redirect there
cd frontend && npm audit --omit=dev                 # react-router high gone

# 3/4/5 — suites (baseline today: 556 green / 72 green; all three add tests)
cd djangotutorial && DJANGO_SETTINGS_MODULE=mysite.test_settings DJANGO_SECRET_KEY=x \
  /usr/bin/python3 manage.py test leaderboard accounts
cd frontend && npm run test:run && npm run lint

# 3 — no N+1: the gallery must stay at a constant query count as the page grows
/usr/bin/python3 manage.py test leaderboard.tests.test_gallery -v 2

# 5 — link-only, by hand. On an event that has a survey_url:
#     click "Přihlásit se"  → modal appears with "Otevřít formulář ↗"
#     the link must point at .../viewform (NOT /edit, no ouid= in the query)
#     "Zrušit účast" must remove the RSVP; "Hotovo" must keep it
#     visiting /events/<slug>/prihlaska directly must now hit the 404 page
curl -s -b cookies.txt localhost:8000/api/v1/events/<slug>/signup-form/   # {"embed_only":true,...}

# 6 — deletion must anonymise, not erase, the points. Note the player id first:
/usr/bin/python3 manage.py anonymize_account <username>
#   → auth.User gone, Profile gone, photo file gone
#   → leaderboard.User still there, name "", email NULL, UserToEvent rows intact
#   → the leaderboard renders that row as "Hráč" and the totals do not move
#   → re-registering with the same e-mail must NOT re-adopt the row

# 7 — the gates
curl -X PUT -b cookies.txt -H "X-CSRFToken: …" \
  localhost:8000/api/v1/events/<past-slug>/rsvp/    # expect 400
curl -s localhost:8000/api/v1/does-not-exist/       # expect JSON, not HTML
curl -si localhost:8000/healthz/                    # 200 + no-store; stop Postgres → non-200
```
