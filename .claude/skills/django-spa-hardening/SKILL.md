---
name: django-spa-hardening
description: Audit and harden a Django + DRF backend paired with a React/Vite SPA — throughput, caching, CDN/edge rules, Open Graph meta tags for link sharing, security (CSRF, IDOR/object-level auth, XSS, cache poisoning, rate limiting), admin protection, and django-allauth social login. Use this skill whenever the user is working on a Django project that serves a JavaScript frontend and mentions performance, throughput, req/s, caching, Cloudflare, WhiteNoise, static files, SEO, link previews, security review, hardening, "is this safe", permissions, DRF viewsets, admin access, Google/OAuth login, or deployment on Render/Fly/Railway — even if they only ask about one narrow piece, because these areas interact and fixing one in isolation often breaks or exposes another.
---

# Django + SPA hardening

Guidance for making a Django/DRF backend with a React (Vite) SPA fast, cacheable, shareable, and secure — without the usual failure mode of optimizing one axis and quietly breaking another.

Respond in the language the user is writing in.

## The single most important idea

Performance and security in this stack are **mostly the same work**. Caching at the edge is also DDoS protection. Moving media to object storage removes both a worker-blocking bottleneck and a path-traversal surface. Fewer bytes served by your own code is faster and safer.

There is exactly **one place where they genuinely conflict**: caching authenticated responses. Treat that as the danger zone and check it explicitly every time.

## Diagnostic order

When the user reports a problem, work down this list rather than jumping to the framework or runtime:

1. **What are the units?** "Thousands of requests" per day is trivial; per second is a different architecture. Ask before designing.
2. **Is it throughput or concurrency?** Little's Law: `L = λ × W`. Node-style event loops raise `L` (connections in flight). They do not raise `λ` if the database is the bottleneck. Most "we need more throughput" problems are N+1 queries.
3. **Is the origin even involved?** If images and static assets hit Django, fix that first — nothing else matters until then.
4. **Where in the request chain does it break?** DNS → CDN → load balancer → gunicorn → Django URLconf → DRF router → React Router. A 404 could come from any layer; identify which before debugging.

## Never recommend these without a very specific reason

These come up constantly and are almost always wrong for a small-to-medium project:

- **Rewriting the backend in Node for throughput.** Node reaches roughly 1000 req/s per core versus Django's ~100–300, but that ceiling is unreachable for most apps (1000 req/s = 86M requests/day). The cost is rebuilding ORM, migrations, auth, permissions, and losing Django admin entirely. Recommend horizontal scaling and caching instead.
- **SSR/Next.js for performance.** `renderToString` is CPU-bound and blocks the event loop — SSR *lowers* origin throughput. SSR is for SEO and LCP. For link previews specifically, server-rendered OG meta tags in the catch-all view give ~90% of the benefit in an hour (see `references/seo-og-tags.md`).
- **JWT in localStorage.** Readable by any XSS by definition and not revocable. When frontend and backend share an origin, `HttpOnly` session cookies are strictly better.
- **Disabling security middleware for speed.** `SecurityMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, and `XFrameOptionsMiddleware` cost tens of microseconds against 10–40 ms of ORM and serialization. Never suggest this as an optimization.
- **`@csrf_exempt` to fix a broken request.** It is never the fix. The frontend is not sending `X-CSRFToken` — fix that instead.

## Highest-value work, in order

If the user asks "where do I start", this is the answer. The first four items take one working day and cover most real risk.

1. **`python manage.py check --deploy`** — five minutes, catches most configuration issues
2. **Object-level authorization on every DRF viewset** — highest actual risk; see `references/security.md`
3. **Security settings: cookies, HTTPS/HSTS, DEBUG, ALLOWED_HOSTS** — a few lines
4. **Admin behind an edge auth layer** (Cloudflare Access or equivalent) — 15 minutes, removes the entire bot-scanning surface
5. **Media to object storage** — biggest throughput win
6. **Cache rules, with the public/personalized split verified**
7. **Rate limiting on login**
8. **OG meta tags** if link sharing matters
9. **CSP in report-only, then enforced**

## Reference files

Read the relevant file when working in that area — each contains concrete settings, code, and verification steps.

- `references/security.md` — six root causes of web vulnerabilities and what maps to each: object-level auth/IDOR, CSRF, cookie flags, HTTPS/HSTS, injection surfaces, CSP, rate limiting, admin hardening
- `references/performance-caching.md` — throughput math, gunicorn tuning, N+1 and DRF serializer cost, media offloading, Vite build output, edge cache rules, and the cache-poisoning danger zone
- `references/seo-og-tags.md` — how SPA routing interacts with scrapers, and the catch-all OG tag pattern
- `references/allauth-google.md` — django-allauth Google setup, the email-match account takeover trap, and the `is_staff` adapter guard

## Verification is part of the work

Never mark a hardening task done without a check the user can run. Every recommendation in the references has one. The two that matter most:

**Cache poisoning check** — log in as user A, load a personalized endpoint, then load the same URL in an anonymous window. Seeing A's data means the CDN is caching authenticated responses.

**IDOR check** — create a second account and try to read and modify the first account's records by ID or slug. A 404 is correct; returning data is a vulnerability.

## Communication style

Explain *why* a mechanism exists, not just what to set. "`HttpOnly` means an XSS payload cannot read the session cookie" lands; "set `HttpOnly = True`" does not, and the user will disable it the first time something breaks.

Give orientational numbers when they help compare orders of magnitude, and label them as orientational rather than presenting them as measurements.
