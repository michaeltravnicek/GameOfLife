# Performance and caching reference

## Throughput math

```
throughput ≈ cores / CPU-time per request
```

A DRF request costs roughly 5–40 ms of CPU (middleware + ORM + serialization). At 10 ms, one vCPU gives ~100 req/s. Reaching 1000 req/s at the origin needs about 10 cores — plus PgBouncer, because hundreds of concurrent connections will exhaust a hosted Postgres before Python does.

These are orientational figures for comparing orders of magnitude, not measurements. Always measure the actual app.

**Concurrency is not throughput.** Little's Law (`L = λ × W`): an event loop raises `L`, the number of requests in flight. If they all queue on the same database, `λ` doesn't move — latency just grows. Most "we need more throughput" reports are N+1 queries.

## Where request cost actually goes

1. HTTP parsing and routing — negligible
2. Middleware chain — small
3. Database queries — usually dominant
4. **Serialization — frequently dominant and usually overlooked**
5. Business logic — small in CRUD apps

DRF serializers build Python objects and validate every field of every row. On a 200-item list this often costs more than the SQL query. For read-only list endpoints, `.values()` plus an `orjson` renderer can cut CPU time roughly in half.

Fix N+1 first — it's usually the single biggest win:

```python
Event.objects.select_related("organizer").prefetch_related("rsvps__user")
```

Profile with django-debug-toolbar locally or django-silk in production. If query count scales with row count, that's the bug.

## Gunicorn

The default `sync` worker handles one request at a time and blocks while waiting on the database. For I/O-bound work use threads:

```bash
gunicorn app.wsgi \
  --worker-class gthread \
  --workers 4 \
  --threads 8 \
  --timeout 30 \
  --bind 0.0.0.0:$PORT
```

The GIL releases during network waits, so threads help here. Watch the connection pool — 4×8 means up to 32 Postgres connections:

```python
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

Note on overload behavior: sync workers fail sharply (backlog, then timeouts and 502s), while event-loop servers degrade gradually (everything gets slow). Neither is free — the second can be worse because degradation is silent.

## Media must not go through the application server

An image served by gunicorn blocks a worker for the whole transfer. A user on a slow connection downloading 2 MB for three seconds holds one of four workers for three seconds. This is the single largest throughput mistake in Django deployments, and on ephemeral filesystems (Render, Fly, Heroku) it also loses files on redeploy.

```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["R2_BUCKET"],
            "endpoint_url": os.environ["R2_ENDPOINT"],
            "querystring_auth": False,
            "custom_domain": "media.example.com",
        },
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```

Presigned direct-to-storage uploads remove the server from the path entirely. See `security.md` for the three things that still need server-side handling.

Generate size variants at upload time and serve WebP/AVIF. This usually beats every server-side optimization combined.

## Static assets and Vite

Content-hashed filenames (`main-a3f2b1.js`) are what make aggressive caching possible: the file never changes, so a new build produces a new name and cache invalidation stops being a problem.

```js
export default defineConfig({
  plugins: [react()],
  base: "/static/dist/",
  build: { outDir: "../static/dist", manifest: true, emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/accounts": { target: "http://localhost:8000", changeOrigin: true },
      "/admin": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
```

The dev proxy matters for correctness, not just convenience: it keeps everything on one origin in development, so CORS isn't needed and cookies behave exactly as they will in production.

`ManifestStaticFilesStorage` + WhiteNoise sets `Cache-Control: max-age=31536000, immutable` on hashed files automatically.

Use `django-vite` to render the script tags from a Django template rather than shipping Vite's `index.html` — it keeps the template under Django's control, which is what makes server-rendered OG tags easy.

**Never put secrets in `VITE_`-prefixed variables.** They're compiled into the bundle and publicly readable. Public identifiers only. Don't serve production source maps publicly; upload them to the error tracker instead.

## Cache layers

Ordered by leverage:

1. **CDN edge** — static and media with long TTLs; public read-only JSON with a short TTL (30–60 s)
2. **Conditional requests** — `ETag`/`Last-Modified` via Django's `@condition` decorator, returning 304 with no body
3. **Redis** for expensive aggregations (leaderboards, counts)
4. **Query optimization** — not caching, but usually a bigger win

```python
from django.core.cache import cache

def get_leaderboard():
    data = cache.get("leaderboard:v1")
    if data is None:
        data = compute_leaderboard()
        cache.set("leaderboard:v1", data, timeout=60)
    return data
```

Short TTL invalidation is simpler than signal-based invalidation and is almost always sufficient.

## The danger zone: caching authenticated responses

This is the one place where optimization creates a security hole.

If a personalized response (profile, user's own records, points) is cached under a key that doesn't include identity, the CDN will serve it to the next visitor. Cache poisoning is one of the most common real data leaks in SPA deployments.

```python
from django.views.decorators.cache import cache_control, never_cache

@never_cache
def my_profile(request): ...

@cache_control(public=True, max_age=60)
def event_list(request): ...
```

**Rule: cache only what is identical for a logged-out visitor.** At the CDN, do not cache anything carrying a `Cookie` or `Authorization` header unless you have specifically verified it's safe. Bypass `/admin/*` and auth paths explicitly.

**Verify every time:** log in as user A, load a personalized endpoint, then load the same URL in an anonymous window. Seeing A's data is the bug.

## Frontend load performance

CSR has a sequential waterfall: HTML → bundle → React boot → fetch → content. Server TTFB can be excellent while the user stares at white for seconds.

Ordered by effect:

1. **Static skeleton in `index.html`** (logo, heading, layout) — FCP drops to TTFB immediately. Cheapest meaningful win.
2. **Route-level code splitting** with `React.lazy()` + `Suspense` — Vite emits separate chunks automatically.
3. **`modulepreload`** — Vite injects it; verify it's present.
4. **Image `loading="lazy"` and `srcset`.**

Measure with Lighthouse under Slow 4G / mobile throttling. Target LCP under 2.5 s. Track p95 latency rather than mean for API endpoints.
