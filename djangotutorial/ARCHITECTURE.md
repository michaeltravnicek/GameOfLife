# Architecture Decisions

This document records key architectural choices for the GameOfLive project, including the reasoning and the conditions under which they should be revisited.

---

## Frontend: Django Templates (not React) — decided 2026-05-01

### Decision
Use Django server-side templates for the frontend. A React migration is planned for the future but deferred.

### Why Django templates now
- **Speed to ship**: ClaudeDesign is already built in vanilla HTML/CSS/JS. Converting to Django templates is 2–3× faster than building the same UI in React.
- **Team fit**: Easier to read and maintain without React knowledge. The codebase stays accessible.
- **Features not yet designed**: Eshop, mobile app, and notifications are future goals, not current ones. Building React infrastructure for undesigned features wastes time.
- **Templates are throwaway anyway**: When React migration happens, the `.html` template files get discarded. The API and CSS tokens survive — so investing in those now is the right preparation.

### What was prepared for future React migration
1. **Django REST Framework (DRF)** — All API endpoints use DRF instead of bare JsonResponse. A future React or mobile app can consume these endpoints immediately with no changes.
2. **CSS design tokens** — All colors, fonts, and spacing use CSS custom properties (`--color-*`, `--font-*`, etc.). A React app imports the same `custom.css` or converts the vars to a JS theme object.
3. **Modular JavaScript** — All JS lives in named functions in separate files. Logic is portable to React hooks.
4. **API-first data** — Every page's data is also available at a `/api/...` endpoint. No server-side-only rendering that would block a React migration.

### When to migrate to React
Pull the trigger when **two or more** of these are true:
- Eshop design is ready and cart state is needed across pages
- Mobile app (React Native) development is starting — code sharing makes React worth it
- Real-time features are needed (live leaderboard, notifications badge, live RSVP counts)
- A dedicated frontend developer joins the team
- Admin UI needs to go beyond what Django admin provides (inline editing, custom dashboards)

### How the migration will work (when it happens)
1. Set up a Next.js project (SSR — good for SEO)
2. Point it at the existing DRF API (no Django changes needed)
3. Migrate one page at a time — React and Django templates can coexist on the same domain via URL routing
4. Start with the most interactive page (profile with tabs/graph) as a proof of concept
5. Move events, leaderboard, home last (they're simpler)

---

## Database: Render PostgreSQL (not Supabase) — decided 2026-05-01

### Decision
Stay on Render's managed PostgreSQL. Supabase evaluated and rejected.

### Why not Supabase
- **No meaningful gain at this scale**: Render PostgreSQL is equivalent to Supabase PostgreSQL for hundreds of users and <1 GB data.
- **Migration cost**: Django's ORM, auth, and admin work perfectly. Migrating to Supabase auth and storage would require rewriting large parts of the app.
- **Google Sheets sync stays in Django**: The cron-based sync is tightly coupled to Django management commands — this stays regardless.
- **Supabase free tier limits are tighter**: 500 MB DB, 1 GB storage, 2 projects vs. Render's paid plan.

### When to revisit Supabase
- If Render's DB pricing becomes a concern at scale
- If real-time subscriptions (live leaderboard) become a priority — Supabase has first-class WebSocket support
- If file storage (event images, profile photos) needs a CDN — Supabase Storage with a CDN would be better than Render's disk

---

## Hosting: Render (current)

### Single Django service handles:
- Web server (Gunicorn)
- Static files (WhiteNoise)
- Media files (uploaded images on Render disk — ephemeral on free tier, persistent on paid)
- Cron job (Google Sheets sync at 4 AM, registered in `build.sh`)

### RAM usage
- Gunicorn workers: ~50–80 MB each
- Total Render service: ~150–250 MB depending on worker count

### If React (Next.js) is added in future
- Second Render service needed: Node.js, ~100–200 MB RAM additional
- Or: use Vercel for Next.js (free tier generous for SSR), Django stays on Render as API-only
