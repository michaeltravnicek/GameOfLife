# GameOfLive — site-readiness audit and plan

> *Audit run 2026-09-19 on branch `review-cleanup` (working tree, plus live probes of
> `https://www.gameofyolo.com`). Four parallel passes: SEO/crawlability, PWA/assets/perf,
> security/ops, accessibility/UX/legal. This is the plan for the "invisible" work — the things a
> site needs that nobody notices until they are missing. Tick items in the tables as they land.*
>
> Confidence labels: **[Certain]** = read in code or observed live with `curl`; **[Likely]** =
> inferred from code but depends on dashboard state (Render/Cloudflare/DNS) that the repo cannot
> see; **[Guessing]** marked explicitly.

## What is already in place — do not redo

The foundation is better than most projects of this size. [Certain] unless noted.

| Area | In place |
|---|---|
| Crawl files | `robots.txt` (`mysite/views.py:150`) with private paths disallowed + `Sitemap:` line; `sitemap.xml` (`mysite/sitemaps.py`) with all visible events + `lastmod`; both tested (`test_sitemap.py`) |
| Link previews | Server-rendered OG/Twitter tags for every request (`mysite/og.py`): home, events, `/hrac/:id`, `/profil/:username`, section titles; consent-gated; 5 MB image fallback; 33 tests in `test_og.py` |
| Canonical host | `http://` and apex both 301 → `https://www.` (Cloudflare) |
| Static caching | Vite hashed `/assets/*` served `immutable`, 10 y, brotli; shell `no-cache, must-revalidate` (`views.py:46`) |
| Security headers | HSTS (short), CSP **enforced**, `X-Frame-Options: DENY`, nosniff, COOP, Referrer-Policy, `SECURE_SSL_REDIRECT`, cookie flags; origin-lock middleware; obscured admin URL that refuses to boot on `admin/` |
| Rate limiting | django-axes + per-account counter; DRF anon/user throttles; scoped throttles on login / register / reset / password change / form submit |
| Ops | `/healthz/` probes DB + cache; backend + frontend Sentry (PII off); `LOGGING`; gunicorn memory budget documented |
| PWA shell | `site.webmanifest` (`standalone`, `lang: cs`, theme colours), `theme-color`, `viewport-fit=cover` |
| A11y shell | `<html lang="cs">`, skip link, global `:focus-visible` ring, `prefers-reduced-motion` in 18 places, `Modal` with focus trap + Escape + restore, Toast `aria-live`, every `<img>` has `alt` |
| UX | scroll-to-top on route change, NotFound page, Czech ErrorBoundary, Web Share on event/profile, past-events archive + filters, empty states on every list, DRF error mapping, disabled-while-busy buttons, self-service account deletion, "remember me" |
| GDPR | Privacy page with correct cookie stance (no banner needed — no analytics, only session/CSRF), anonymising deletion, policy version pinned in settings and page |

---

# Phase 1 — Broken or embarrassing right now (ship first, ~1 day)

These are not improvements; they are things currently wrong on the live site.

| # | Finding | Evidence | Fix | Verify |
|---|---|---|---|---|
| 1.1 | **Browser Sentry is blocked by the enforced CSP.** Live header is `connect-src 'self'`; the DSN host `*.ingest.de.sentry.io` is only added via the optional env `CSP_EXTRA_CONNECT_SRC`. No frontend error has reached Sentry since CSP was enforced. [Certain] | `settings.py:259-273`, `frontend/.env.production:12`, live `curl -I` | Add the DSN host to `connect-src` by default (derive it from the frontend DSN or hard-code `https://o4511775685279744.ingest.de.sentry.io`); add `report-uri`/`report-to` pointing at Sentry's CSP endpoint so future violations are visible; test asserting the Sentry host in `test_csp.py` | `curl -sI https://www.gameofyolo.com/ \| grep -i content-security` shows the host; throw a test error in the console and see it in Sentry |
| 1.2 | **Privacy policy ships with `[DOPLNIT]` placeholders and an internal "Než tohle zveřejníš" note**, while registration collects consent against it. [Certain] | `PrivacyPage.jsx:24-37,117,121` | Fill in: controller name, IČO, address, contact e-mail, Render region (Frankfurt if EU), e-mail provider. Remove the note. Bump `POLICY_VERSION` + `PRIVACY_POLICY_VERSION` together | `grep -c DOPLNIT frontend/src/pages/Privacy/PrivacyPage.jsx` → 0 |
| 1.3 | **The SPA never sets `document.title`.** After the first client-side navigation every tab, bookmark, history entry and screen-reader announcement carries the previous page's title. [Certain] | `grep -r document.title frontend/src` → 0 hits; only `og.py` sets it for the initial HTML | Add `hooks/usePageTitle.js` (`useEffect` → `document.title = \`${title} — Game of Life\``) and call it from every page; move focus to `#obsah` (or the `h1`) on route change in `App.jsx`'s ScrollToTop | Navigate home → event → leaderboard; tab title changes each time |
| 1.4 | **Soft 404s.** Unknown paths, unknown event slugs, `/favicon.ico`, `/apple-touch-icon*.png`, `/.well-known/*` all answer **200 + index.html + a CSRF cookie**. The 404-for-missing-slug fix exists but is **uncommitted** (`views.py:84`). [Certain — live `curl`] | `urls.py:127-130` catch-all, `og.py:338-355` | (a) Commit the `exists=False → 404` change with an HTTP-level test; (b) put real `favicon.ico`, `apple-touch-icon.png` in `frontend/public/` (WhiteNoise answers before the catch-all); (c) extend the catch-all's negative look-ahead so `\.(ico|png|xml|txt|php|json)$` and `.well-known/` return a plain 404 instead of the shell; (d) `NotFoundPage` renders `<meta name="robots" content="noindex">` | `curl -o /dev/null -w '%{http_code}' https://www.gameofyolo.com/events/nope` → 404; same for `/favicon.ico` (or 200 with `image/x-icon`) |
| 1.5 | **iOS / Safari icons are broken.** `apple-touch-icon` and favicon are WebP — Safari renders neither; the manifest has no PNG, no 192 px, no `maskable`; `favicon.svg` exists but is not linked; the manifest is served as `application/octet-stream`. The stated goal ("add to home screen at events") fails on every iPhone. [Certain] | `index.html:5,12`, `site.webmanifest`, live `curl -I /site.webmanifest` | Generate from `image-src/logos/GOL_main_logo_pink.png` via `optimize-images.js`: `apple-touch-icon.png` 180², `icon-192.png`, `icon-512.png`, `icon-512-maskable.png` (logo on `#1a0f0a` with safe-zone padding), `favicon.ico` (32²). Link `favicon.svg` + `favicon.ico`; manifest icons → PNGs with `purpose: any` and `maskable`; add `WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}` | Add to home screen on an iPhone and an Android; Chrome DevTools → Application → Manifest shows no warnings |
| 1.6 | **HSTS is 300 s**, so `includeSubDomains`/`preload` are off (`check --deploy` W005, W021). [Certain] | `settings.py:169-171` | Env on Render: `SECURE_HSTS_SECONDS=86400` for a week, then `31536000`. Tick the RUNBOOK item | `curl -sI … \| grep strict` → `max-age=31536000; includeSubDomains; preload` |
| 1.7 | **Transactional e-mail is unverified.** `DEFAULT_FROM_EMAIL` defaults to `noreply@gameofyolo.cz` (site is `.com`), SMTP creds default to empty, and `password_reset_api` swallows send failures and returns 200 — a broken mailer is invisible. [Certain for code; Likely for prod env] | `settings.py:882-891`, `accounts/api/views.py:189-197` | Set `DEFAULT_FROM_EMAIL=Game of Life <noreply@gameofyolo.com>`; confirm `EMAIL_HOST_*` on Render; add SPF/DKIM/DMARC records for the sending provider; log a **warning at boot** when `EMAIL_HOST_PASSWORD` is empty in prod; add the provider to the privacy page (1.2) | Request a password reset on prod; check headers for `spf=pass dkim=pass` |

---

# Phase 2 — SEO and crawlability (~1 day)

The site is a Czech community site; realistic search traffic is people googling event names and
"Game of Life Brno". Everything below makes those hits land on the right page with a proper card.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 2.1 | No `<link rel="canonical">`; `og:url` follows the request host and keeps the query string. [Certain] | `og.py:196,250,359-383` | Add `SITE_URL = "https://www.gameofyolo.com"` in settings; `render_tags` emits `<link rel="canonical" href="{SITE_URL}{path}">` (path only, no query) and uses it for `og:url`; sitemap/robots use it instead of `request.build_absolute_uri` |
| 2.2 | No structured data anywhere. [Certain] | `grep -r ld+json` → 0 | In `render_tags`: `schema.org/Event` JSON-LD for `/events/<slug>` (name, startDate, location, image, url, `eventStatus`, organizer = Game of Life) — `_event_metadata` already loads the fields; `Organization` + `WebSite` on `/`. Use `json.dumps` and escape `</` — never f-string HTML |
| 2.3 | Home card is weak: title `👾 Život je hra.` without the brand, emoji description, `og:image` is a **1440×1920 portrait WebP** (LinkedIn/some messengers won't render WebP; centre-crop on 1.91:1). Code already flags this as a TODO. [Certain] | `og.py:43-53` | Produce a 1200×630 PNG/JPEG social card (`frontend/image-src/og-default.png` → copied unoptimised), title `Game of Life — Život je hra`, emit `og:image:width/height/alt`, `og:image:type` |
| 2.4 | Section pages share `DEFAULT_DESCRIPTION`; `/ochrana-osobnich-udaju` has no title override and is not in the sitemap; static sitemap entries lack `lastmod`. [Certain] | `og.py:100-106`, `sitemaps.py:24-30` | Per-page descriptions in `_PAGE_TITLES` → `_PAGES` dict; add privacy page; `lastmod` from the latest event `updated_at` for `/` and `/events` |
| 2.5 | robots.txt misses `/accounts/`, bare `/profil` (own profile; `/profil/<username>` must stay allowed), `/healthz/`, `/whoami/`. [Certain] | `views.py:150-182` | Add lines; extend `RobotsTxtTests` |
| 2.6 | No `noindex` signal on private/auth routes or on `/api/`. [Certain] | no `X-Robots-Tag` anywhere | Middleware setting `X-Robots-Tag: noindex` on `/api/`, `/accounts/`, the admin prefix, and on the SPA shell when the path matches a private route list (`/prihlasit`, `/registrace`, `/upravit-profil`, `/sprava/`, `/events/vytvorit`, `/events/*/upravit`, `/profil$`) |
| 2.7 | `og:type` is always `website`; events have no time-bound signals. [Certain] | `og.py:368` | Emit `og:type=event`-equivalent via JSON-LD (2.2) — OG itself has no event type worth using; leave `website` |
| 2.8 | No Search Console verification artefact; unknown whether the property exists. [Likely — DNS-TXT verification would leave no trace] | grep `google-site-verification` → 0 | Verify the domain in Google Search Console (DNS TXT), submit `sitemap.xml`, check Coverage for the soft-404s from 1.4 once fixed |
| 2.9 | `sitemap.xml` carries an edge-added `X-Robots-Tag: noindex, noodp, noarchive` that no repo code explains. [Certain it is there; Guessing it is a Cloudflare Transform Rule] | live header | Find the rule in Cloudflare; scope it to the admin path only (that is what the RUNBOOK intends) and document it |
| 2.10 | Cheap headers/files missing: `Permissions-Policy`, `/.well-known/security.txt` (RFC 9116), `/.well-known/change-password` → `/upravit-profil`. [Certain] | `urls.py`, `frontend/public/` | `security.txt` + `change-password` as small Django views (before the catch-all); `Permissions-Policy: camera=(), microphone=(), geolocation=(self), payment=()` via `SecurityMiddleware` subclass or Cloudflare Transform Rule (note: geolocation **must** stay `self` — check-in uses it) |
| 2.11 | Tests: no HTTP-level 404 for a missing slug, nothing on canonical/description/JSON-LD. | `test_og.py:253-283` | Add with each item above |

---

# Phase 3 — Performance and caching (~1–2 days)

TTFB is ~100 ms and JS is already hashed/immutable/brotli — the origin is fine. The remaining weight is fonts, images and cache TTLs on non-hashed files.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 3.1 | **~2.6 MB of unsubsetted TTF fonts** (12 files: Helvetica ×5 = 1.55 MB, IBM Plex Mono ×5 = 883 kB, Ringold ×2), `format('truetype')`, served as `application/octet-stream`, **cached 1 h at origin and 4 h at the edge**, not covered by any Cloudflare rule. The preloaded face is the *italic mono*, not the body font. `Helvetica-Oblique.ttf` alone is 597 kB. [Certain] | `styles/colors_and_type.css:6-75`, `index.html:19`, live headers | Convert to WOFF2 subset to Latin + Latin-Ext (`pyftsubset --flavor=woff2 --unicodes="U+0000-00FF,U+0100-017F,U+2000-206F,U+20AC"`); expect ~5–8× smaller (orientational). Drop faces not used in CSS (audit `font-style: italic`/`font-weight` usage first). Preload the body regular face instead. Import fonts through Vite (`src/assets/fonts/`) so they get hashed names and fall under the immutable rule |
| 3.2 | R2 uploads are stored **without `Cache-Control`**; browser TTL for media is whatever Cloudflare stamps (currently 4 h). Filenames are already collision-suffixed, so they are safe to mark immutable. [Certain] | `settings.py:794-819`, live `curl -I img.gameofyolo.com/…` | `"object_parameters": {"CacheControl": "public, max-age=31536000, immutable"}` in the S3 storage `OPTIONS`; re-stamp existing objects with a one-off `aws s3 cp --metadata-directive REPLACE` (or the `migrate_media_to_s3` command) |
| 3.3 | Cloudflare cache rules target `/static/` (Django admin only); the real Vite paths `/assets/`, `/img/`, `/fonts/` have no long-TTL rule. [Certain from RUNBOOK; Likely for the dashboard] | `security/RUNBOOK.md:75-108` | Add a Cache Everything rule with Edge TTL 1 y for `/assets/*` (hashed) and 1 d for `/img/*`, `/fonts/*` (or hash them via Vite per 3.1 and drop the rule). Update the RUNBOOK table |
| 3.4 | `WHITENOISE_IMMUTABLE_FILE_TEST` only matches `.js|.css`; hashed images/fonts Vite emits into `/assets/` get 1 h. [Certain] | `settings.py:851` | Widen the extension group to `(js\|css\|woff2\|png\|webp\|svg)` |
| 3.5 | No `<link rel="preconnect" href="https://img.gameofyolo.com">` — one extra TLS handshake before the first event image. [Certain] | `index.html` | Add `preconnect` + `dns-prefetch` |
| 3.6 | Images: 0/25 `decoding="async"`, 22/25 lack `width`/`height`, `<picture>` used once, the Hero "preload" is injected in a `useEffect` (after hydration — not a real preload). [Certain] | `Hero.jsx:91-101`, `LazyImg.jsx` | Add `width`/`height` (or `aspect-ratio`) + `decoding="async"` to `LazyImg`/`EventCard`; server-render the first hero slide's `<link rel="preload" as="image">` in `og.inject` (the shell is already rewritten per request) |
| 3.7 | Public API endpoints are edge-cached 60–300 s but never 304-revalidated — every expiry re-serialises. [Certain] | `leaderboard/api/views.py:304,344,432…` | `Last-Modified` from `max(updated_at)` via `django.views.decorators.http.condition` on events list/detail and leaderboard; keep `Vary` minimal |
| 3.8 | No Sentry `release` (backend or frontend), no sourcemaps → minified traces; no web-vitals. [Certain] | `settings.py:959-974`, `sentry.js`, `vite.config.js` | `release=os.getenv("RENDER_GIT_COMMIT")` backend; `@sentry/vite-plugin` with `release.name` from the same SHA and `sourcemaps.filesToDeleteAfterUpload` so maps never ship; optionally `Sentry.browserTracingIntegration` at a low sample rate for LCP/CLS |
| 3.9 | `manualChunks` unset; Leaflet rides with `EventDetailPage` (fine as long as it stays lazy — verify after each dependency change). [Likely] | `vite.config.js` | Add a CI bundle-size check (`npm run build` + `du`) rather than tuning chunks now |
| 3.10 | Service worker / offline: **none**. | — | **Decision, not a task.** A SW adds an update-staleness class of bugs; for a site people open at events with flaky signal, an app-shell + last-events cache via `vite-plugin-pwa` (`registerType: 'autoUpdate'`) is justified — but only after 1.5 makes install work at all. Defer to Phase 6 |

---

# Phase 4 — Ops, deployment hygiene, security depth (~1–2 days, partly click-ops)

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 4.1 | **Backups are a document, not a practice.** RUNBOOK §10 has blank fields (plan, retention, last restore date); no dump job in the repo; R2 versioning unchecked. [Certain for repo; Likely for Render's own retention] | `security/RUNBOOK.md` §10, `GAP_ANALYSIS.md:409` | Render cron: `pg_dump \| gzip \| aws s3 cp` to a **separate** R2 bucket with 30-day lifecycle; enable R2 object versioning on the media bucket; do one restore drill into a scratch DB and write the date into the RUNBOOK |
| 4.2 | No external uptime monitor; only Render's own health check. [Likely] | no mention in any doc | UptimeRobot/BetterStack on `/healthz/` (every 1–5 min, alert on 503) — free tier suffices; document in RUNBOOK |
| 4.3 | CI runs tests only — no `npm run lint` (CLAUDE.md and GAP_ANALYSIS claim it does), no `vite build`, no `collectstatic`, no `check --deploy`, no `makemigrations --check`, no dependency audit; Render deploys `main` regardless. [Certain] | `.github/workflows/tests.yml` | Add jobs: `npm run lint`, `npm run build`, `manage.py makemigrations --check --dry-run`, `manage.py check --deploy` (with dummy prod env), `pip-audit`, `npm audit --audit-level=high`. Enable branch protection on `main` requiring the workflow (GitHub setting) |
| 4.4 | No Dependabot/Renovate; `package.json` uses caret ranges with no `engines`; no `.nvmrc`; Render Node version unpinned (Vite 8 needs ≥ 20.19). [Certain] | `.github/`, `frontend/package.json` | `.github/dependabot.yml` (pip + npm + actions, weekly, grouped); `"engines": {"node": ">=20.19"}` + `.nvmrc`; set `NODE_VERSION` on Render |
| 4.5 | No gunicorn access log; the only per-request record is Cloudflare's. [Certain] | `gunicorn.conf.py`, `start.sh:37` | `accesslog = "-"` with a compact format including `%(D)s` (µs) — Render captures stdout |
| 4.6 | No `handler500`; an exception escaping DRF under `/api/` returns Django's HTML page. [Certain] | `urls.py:135` | JSON `handler500` for `/api/` paths, mirroring `api_not_found` |
| 4.7 | RUNBOOK contradicts code: §7 says CSP is report-only (code enforces by default), §6 shows gunicorn `4×8` vs the `3×2` in `gunicorn.conf.py`. [Certain] | `security/RUNBOOK.md` §6, §7 | Fix both; add a "verified on <date>" line to each section |
| 4.8 | No maintenance mode. | — | Cloudflare Worker/Page Rule returning a static 503 page is the cheapest (no deploy needed); keep a `maintenance.html` in `frontend/public/` for it |
| 4.9 | Uploads (`photo_upload`, `event_images_upload`, `profile_photo_upload`), `event_checkin`, `event_feedback`, `event_rsvp`, `photo_like` ride only the generic 300/min user throttle; image decodes are the expensive path in the memory budget. [Certain] | `leaderboard/api/views.py:217-654`, `accounts/api/views.py:323-346` | Scoped throttles: uploads 20/hour, check-in 30/hour, feedback/RSVP 60/hour, likes 120/min |
| 4.10 | Admin has no 2FA/honeypot; protection relies on Cloudflare Access, which is an unchecked RUNBOOK item. [Certain for repo; Likely for Cloudflare] | `requirements.txt`, RUNBOOK §1 | Confirm Cloudflare Access is on (tick the box); add `allauth.mfa` (TOTP) for `is_staff` users — allauth is already installed |
| 4.11 | CSP `font-src` allows `fonts.gstatic.com` and `style-src` allows `fonts.googleapis.com`, but nothing loads Google Fonts. Dead allowance — and removing it is also the GDPR-clean answer. [Certain] | `settings.py:266-267`, `index.html` | Remove both; adjust `test_csp.py:47-50` |
| 4.12 | `CSRF_TRUSTED_ORIGINS` includes four localhost entries unconditionally. [Certain] | `settings.py:309-317` | Gate on `DEBUG` |

---

# Phase 5 — Accessibility and user-facing completeness (~2 days)

Add `eslint-plugin-jsx-a11y` first (5.1) — it catches about half of this list mechanically and keeps it fixed.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 5.1 | No `eslint-plugin-jsx-a11y`. | `frontend/eslint.config.js` | Add with `recommended`; fix what it reports; CI runs lint (4.3) |
| 5.2 | **Two `<main>` landmarks on 12 pages** (`App.jsx:53` + page-level). | `EventsPage.jsx:225` etc. | Page-level `<main>` → `<div>`/`<section>` |
| 5.3 | **Gallery tiles and event-gallery figures are mouse-only** (`<div onClick>`); Lightbox lacks `role="dialog"`, `aria-modal`, focus trap. | `GalleryPage.jsx:302`, `EventDetailPage.jsx:564`, `Lightbox.jsx:108` | Tiles → `<button>` (or `role="button" tabIndex=0 onKeyDown`); reuse `Modal`'s trap in `Lightbox` |
| 5.4 | Contrast: white on `#e15463` ≈ 3.7:1 (all primary buttons at 11–14 px), pink on cream ≈ 3.3:1 — fail AA. [Certain — computed] | `Button.css:11-42`, `EventCard.css:37,51` | Use `--color-pink-dark #c1394a` for text-bearing pink surfaces, or ≥ 18.5 px bold text. Keep pink-on-dark (5.1:1 passes) |
| 5.5 | Hero auto-advances every 5 s with no pause and ignores reduced-motion (WCAG 2.2.2). | `Hero.jsx:117-121` | Respect `prefers-reduced-motion`, pause on hover/focus, add a pause button |
| 5.6 | No `h1` on Login/Register/Forgot/Reset; EventDetail's name is only an `h2` and only when a description exists. | `LoginPage.jsx:50`, `EventDetailPage.jsx:434-448,531` | Promote the poster title to `h1`; auth pages `h2` → `h1` |
| 5.7 | Unlabelled inputs: `SearchInput` (no label, `type="text"`), social handles, feedback textarea; `PillTabs` has no selected-state ARIA; `role="radiogroup"` wraps `aria-pressed` buttons. | `SearchInput.jsx:11`, `EditProfilePage.jsx:413`, `EventDetailPage.jsx:884-899`, `PillTabs.jsx:53` | `aria-label` + `type="search"`; `role="radio" aria-checked`; `aria-pressed` on tabs; `role="alert"` on `.auth-error` |
| 5.8 | No route-change focus management. | `App.jsx:29-46` | In ScrollToTop: `document.getElementById('obsah')?.focus()` (with `tabIndex=-1`) after navigation |
| 5.9 | Event detail lacks **add-to-calendar** (`.ics` / Google Calendar link) and an **external map link** despite storing date, time and coordinates. | `EventDetailPage.jsx:446,540` | `GET /api/v1/events/<slug>/ics/` (public, cacheable) + Google Calendar `render?action=TEMPLATE` link; `https://mapy.cz/zakladni?q=<lat>,<lon>` + `geo:` link next to the place name |
| 5.10 | Footer: Instagram `href="#"`, hardcoded © 2026, no e-mail, no `tel:` link; page called "Events" / "Eventy" / "Kalendář" in three places. | `Footer.jsx:14,27,30`, `EventsPage.jsx:150`, `Nav.jsx` | Fix link, `new Date().getFullYear()`, `mailto:`/`tel:`, one name |
| 5.11 | No password-rule hints before submit; no upload size hint; gallery upload has no client-side size check at all. | `RegisterPage.jsx:123`, `GalleryPage.jsx:80-88`, `useImagePreview.js:16` | Hint text ("min. 8 znaků"), "max. 8 MB, JPG/PNG/WebP" near every file input; apply `useImagePreview`'s guard to gallery upload |
| 5.12 | No Terms of Service, no imprint/provozovatel page, no data-export endpoint although the privacy page promises portability (Art. 20). | `PrivacyPage.jsx:140`, `accounts/api/` | `GET /api/v1/auth/me/export/` returning JSON of profile + attendance + points (session-only, throttled 5/hour); short `/podminky` page; imprint block in footer or privacy page |
| 5.13 | "Profil nenalezen" is inline text with no heading or link back. | `ProfilePage.jsx:90`, `PlayerPage.jsx:79` | Reuse the EventDetail not-found pattern |
| 5.14 | No `@media print` — dark background + fixed grain prints black. | `global.css:6` | Minimal print sheet: white bg, hide nav/footer/grain, black text |
| 5.15 | Frontend tests: nothing for `Modal` focus trap, `Lightbox`, `Nav`, auth pages, `EventDetailPage`, `api.js` interceptors. | `frontend/src/**/*.test.jsx` | Add as each component above is touched |

---

# Phase 6 — Decisions to make, not tasks to do

| Topic | Options | Recommendation |
|---|---|---|
| Service worker / offline | (a) none (b) app-shell + cached events list via `vite-plugin-pwa` | (b), but only after Phase 1.5 — an installable icon matters more than offline, and a SW without a release process causes "why do I see the old version" reports |
| E-mail verification | already decided **off** (GAP_ANALYSIS) | Keep off; revisit only if fake accounts appear. 1.7 (working mailer) is a prerequisite anyway |
| Event notifications (e-mail/push) | none today | Not until 1.7 + a clear opt-in on the profile page; push needs a SW (above) |
| Analytics | none today (privacy page relies on this) | If wanted, Cloudflare Web Analytics (cookieless) — update the privacy page and CSP `script-src` in the same commit |
| Number formatting | raw integers | `Intl.NumberFormat('cs-CZ')` when points exceed 4 digits |

---

# Suggested order and effort

| Order | Item | Effort | Depends on |
|---|---|---|---|
| 1 | 1.1 Sentry CSP + report-uri | 1 h | — |
| 2 | 1.2 Privacy placeholders | 1 h + info from owner | — |
| 3 | 1.4 Real 404s (commit + static files + look-ahead + noindex) | 2 h | — |
| 4 | 1.5 Icons + manifest | 2 h | — |
| 5 | 1.3 `usePageTitle` + focus on navigate (covers 5.8) | 2 h | — |
| 6 | 1.6 HSTS env, 1.7 e-mail sender + SPF/DKIM | 1 h + DNS | — |
| 7 | 2.1–2.6 canonical, JSON-LD, social card, descriptions, robots, noindex | 4 h | 1.4 |
| 8 | 2.8, 2.9 Search Console, edge X-Robots rule | 1 h click-ops | 7 |
| 9 | 2.10 security.txt, change-password, Permissions-Policy | 1 h | — |
| 10 | 3.1 WOFF2 fonts, 3.4, 3.5 | 3 h | — |
| 11 | 3.2 R2 Cache-Control + re-stamp, 3.3 Cloudflare rules | 2 h | — |
| 12 | 3.8 Sentry release + sourcemaps | 2 h | 1.1 |
| 13 | 4.3 CI lint/build/check, 4.4 Dependabot + Node pin | 2 h | — |
| 14 | 4.1 Backups running + restore drill, 4.2 uptime monitor | 3 h | — |
| 15 | 4.5–4.7, 4.9, 4.11, 4.12 ops/security small items | 3 h | — |
| 16 | 5.1–5.8 a11y core | 1 day | — |
| 17 | 5.9 ics + map, 5.10–5.14 | 1 day | — |
| 18 | 3.6, 3.7 images + conditional GET | 4 h | — |
| 19 | 4.10 admin MFA | 3 h | — |
| 20 | Phase 6 decisions | — | 4, 6 |

Total: roughly 8–9 working days, of which Phase 1 (one day) removes everything that is currently
*wrong* rather than merely missing.

---

# Verification checklist (run after each phase)

```bash
# 404 semantics
for p in /events/nope-123 /favicon.ico /.well-known/security.txt /nonsense; do
  curl -s -o /dev/null -w "$p %{http_code} %{content_type}\n" https://www.gameofyolo.com$p; done

# Headers
curl -sI https://www.gameofyolo.com/ | grep -iE 'strict|content-security|permissions-policy|x-robots'
curl -sI https://www.gameofyolo.com/api/v1/events/ | grep -i x-robots

# Cards + structured data
curl -s -A facebookexternalhit/1.1 https://www.gameofyolo.com/events/<slug> \
  | grep -oE '<(link rel="canonical"|meta property="og:image[^"]*"|script type="application/ld)[^>]*>'

# Caching
curl -sI https://www.gameofyolo.com/assets/<hashed>.woff2 | grep -i cache-control      # immutable
curl -sI https://img.gameofyolo.com/event_images/<file> | grep -i cache-control        # max-age=31536000

# Django
cd djangotutorial && MODE=PRODUCTION DJANGO_SECRET_KEY=x ADMIN_URL=x/ ALLOWED_HOSTS=www.gameofyolo.com \
  DATABASE_URL=sqlite:////tmp/x.db .venv/bin/python manage.py check --deploy         # 0 issues

# Frontend
cd frontend && npm run lint && npm run build && npx vitest run
```

External: Facebook Sharing Debugger, Google Rich Results Test (event page), Lighthouse (mobile,
PWA + a11y ≥ 90), `https://securityheaders.com`, `https://hstspreload.org` once 1.6 is at a year.
