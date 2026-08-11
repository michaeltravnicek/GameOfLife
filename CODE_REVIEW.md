# Code Review — architecture, duplication, React best practices

*Date: 2026-07-03 · Branch: `react` · Method: jscpd duplication scan (frontend + backend), full read of the hotspot files, checked against the Vercel react-best-practices rules.*

## Changes made during this review

- **Removed the `/alt` homepage experiment**: deleted `HomePageAlt.jsx`, `HomePageAlt.css`, its route in [App.jsx](frontend/src/App.jsx), and `hooks/useCountUp.js` (only HomePageAlt used it). Build + all 37 tests green.
- **Fixed ESLint config**: [eslint.config.js](frontend/eslint.config.js) now ignores `android/` and `ios/` — it was linting Capacitor's minified bundle copies, producing ~364 phantom errors that drowned out the ~31 real ones. (Note: `npm run lint` was never actually clean; a pipe was masking the exit code in earlier runs.)

---

## The honest overall picture

This codebase is **better architected than most hobby projects** — it does not need a broad rewrite. The backend has a real services layer, read-path serializers, centralized cache keys with TTLs, and `jscpd` found **zero copy-paste duplication in the Python code**. The frontend has route-level code splitting, a documented homegrown SWR cache with dedup + retry, and hover preloading. The problems below are localized. Rewrite the two hotspots, fix the small stuff opportunistically, and leave the rest alone.

---

## 🔴 Rewrite candidate #1: CreateEventPage / EditEventPage (frontend)

**The worst duplication in the repo.** [CreateEventPage.jsx](frontend/src/pages/Events/CreateEventPage.jsx) (309 lines) and [EditEventPage.jsx](frontend/src/pages/Events/EditEventPage.jsx) (334 lines) are ~85 % identical — jscpd found 8 clone blocks covering the form-state shape, `setField`, the entire `FormData` assembly, and all ~200 lines of section JSX (Základy / Čas a body / Vizuál / Kategorie / Obsah / Poloha / Viditelnost).

**Why it matters practically:** every new event field must be added in *both* files, and they have **already drifted** — Edit sends `end_date` always (`formData.append('end_date', form.end_date || '')`) while Create sends it only when set. That asymmetry is exactly the class of bug this duplication breeds.

**Recommended shape** (one afternoon of work):

```
pages/Events/
  EventForm.jsx        ← all sections + form state + setField (~280 lines, moves once)
  eventFormData.js     ← buildEventFormData(form, poster, logo, categories, allCategories)
  CreateEventPage.jsx  ← ~40 lines: empty initial values, onSubmit={createEvent}, copy "Vytvořit"
  EditEventPage.jsx    ← ~70 lines: load event → initial values, onSubmit={updateEvent}, copy "Upravit"
```

`EventForm` takes `initialValues`, `onSubmit`, `submitLabel`, `heading` — the two pages become thin wrappers. This also gives you one place to fix the `end_date` asymmetry deliberately.

## 🔴 Rewrite candidate #2: event_create / event_update (backend)

[api/views.py:386-552](djangotutorial/leaderboard/api/views.py#L386-L552) — 165 lines of hand-rolled field parsing that *semantically* duplicate each other (jscpd misses it because Update wraps every field in `if 'x' in request.data`). This is the one place the backend bypasses its own serializer layer: reads go through `EventDetailSerializer`, but writes re-implement parsing, coercion, and Czech error messages by hand — twice.

**Recommended shape:** one `EventWriteSerializer` used by both views — `EventWriteSerializer(data=…)` for create, `EventWriteSerializer(event, data=…, partial=True)` for PATCH. That collapses ~165 lines to ~60, unifies validation, and kills two extra problems for free:

- `event_update` ends with `except Exception as exc: return Response({"error": str(exc)}, 400)` — this **leaks internal exception text to the client** and misreports server bugs as client errors. Delete it; let real errors 500.
- `from leaderboard.models import Category` is imported inline twice inside the same module that already imports from `leaderboard.models`.

Keep the `full_clean(exclude=['date'])` semantics by mirroring them in the serializer (`date` optional, model requires it — that quirk deserves one comment in one place, not two).

## 🟠 Duplication worth extracting (smaller)

1. **Auth page scaffolding (4 files).** Login / Register / ForgotPassword / ResetPassword each repeat the same ~25-line hero + auth-card wrapper (5 jscpd clones). Extract an `AuthShell` layout component (`title`, `sub`, `children`); each page keeps only its form. Bonus: the hero hardcodes **„Sezóna 2025/26"** in JSX — it's July 2026, this goes stale in two months; feed it from the seasons API or a constant.
2. **Rank + totals math duplicated across apps (backend).** The "aggregate points/events, then count users with more points" block exists identically in [accounts/services.py:93-107](djangotutorial/accounts/services.py#L93-L107) (`profile_payload`) and [leaderboard/services/leaderboard.py:200-213](djangotutorial/leaderboard/services/leaderboard.py#L200-L213) (`player_payload`). Extract `totals_and_rank(lb_user)` into `leaderboard/services/` — accounts already depends on leaderboard, so this also reduces the awkward *reverse* imports (`leaderboard` importing `accounts.services` inside function bodies to dodge the circular dependency). Direction to enforce: **accounts → leaderboard, never back**.
3. **EventsPage upcoming/past grids** ([EventsPage.jsx:264-289](frontend/src/pages/Events/EventsPage.jsx#L264-L289)) — two identical 10-line grid blocks; a tiny `EventGroup` component removes the last frontend clone. Optional.
4. **EventCardAlt internal clones** — known-temporary design exploration (marked `TEMPORARY` in code, tracked in memory). Not worth cleaning; worth *deciding*: pick the winning card variant, fold it into `EventCard`, delete `EventCardAlt` + the `?cards=` switcher, and the clones disappear with it.

## 🟡 Real lint findings (21 errors, 10 warnings in `src/` after the config fix)

Triage — most are **not** bugs:

- **`react-refresh/only-export-components` (4 errors)** — [ToastProvider.jsx](frontend/src/components/Toast/ToastProvider.jsx) exports `toast`, [AuthContext.jsx](frontend/src/context/AuthContext.jsx) exports `useAuth`, [PlayerRow.jsx](frontend/src/components/PlayerRow/PlayerRow.jsx) exports a helper. Only affects hot-reload granularity in dev, zero production impact. Fix lazily by moving non-component exports to sibling files.
- **`react-hooks/set-state-in-effect` (8 errors)** — the new v7 rule firing mostly on legitimate patterns (Nav closing menus on route change, AuthContext session probe on mount, Gallery clamping an index). Two are worth actually fixing because they're derived state, not synchronization: `setFbDone` in [EventDetailPage.jsx:47](frontend/src/pages/EventDetail/EventDetailPage.jsx#L47) and `setCities` in [EventsPage.jsx:99](frontend/src/pages/Events/EventsPage.jsx#L99) can both be computed during render (`const fbDone = fbDoneOverride ?? event?.feedback_given`), removing a render cycle each.
- **`exhaustive-deps` warning in [EditEventPage.jsx:83](frontend/src/pages/Events/EditEventPage.jsx#L83)** — the load effect uses `poster`/`logo` but depends only on `[slug]`. Works today because the hook objects are recreated per render (which is *why* they can't go in the deps). The EventForm rewrite should make `useImagePreview` return stable callbacks (`useCallback` inside the hook); then the deps become honest.
- **Dead code:** `divider` in [PageHero.jsx:19](frontend/src/components/PageHero/PageHero.jsx#L19), two stale `eslint-disable no-console` directives.

## ✅ Where the architecture is right (don't touch)

- **Frontend data layer** — [queryCache.js](frontend/src/services/queryCache.js) is a well-documented mini-SWR (TTL, stale-while-revalidate, in-flight dedup, retry with backoff on 5xx/network only), [api.js](frontend/src/services/api.js) is the single axios client handling CSRF/web vs token/native in one place, [routePreload.js](frontend/src/services/routePreload.js) preloads chunk + data on link hover. This satisfies the react-best-practices rules (`client-swr-dedup`, `bundle-preload`, `async-parallel` — EditEventPage even uses `Promise.all` for its two fetches) with zero dependencies.
- **Bundle discipline** — every route lazy-loaded, Leaflet isolated in its own 161 kB chunk that only map pages download, main bundle 194 kB. `rerender-*` rules: EventsPage/pages use `useMemo`/`useCallback` where it counts.
- **Backend layering** — views are thin (parse → service/serializer → Response), services own the queries, `cache_config.py` centralizes keys/TTLs, checkin geometry isolated in `checkin.py`. Zero jscpd clones across 3 677 Python lines.
- **CSS** — zero duplication across 40 files; per-page styles + shared tokens work.

## Suggested order of attack

| # | Task | Size | Payoff |
|---|------|------|--------|
| 1 | `EventForm` extraction (frontend) | ~½ day | kills 8 of 16 clones + the `end_date` drift |
| 2 | `EventWriteSerializer` (backend) | ~½ day | −100 lines, one validation path, removes the `str(exc)` leak |
| 3 | Decide event-card winner → delete `EventCardAlt` + switcher | decision + 1 h | kills 3 clones + dead route param |
| 4 | `AuthShell` + season string from API | ~2 h | kills 5 clones + a time bomb |
| 5 | `totals_and_rank()` helper + one-way app dependency | ~1 h | removes cross-app import smell |
| 6 | Lint cleanup (derived state ×2, refresh-only exports, dead code) | ~1 h | lint actually green, trustworthy in CI |

After 1–4 the jscpd clone count drops from 16 to ~0 and both "rewrite" items are gone — nothing else in the repo warrants restructuring.
