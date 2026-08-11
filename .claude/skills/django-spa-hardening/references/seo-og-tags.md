# SEO, link previews, and SPA routing

## Two routers, one URL

An SPA served by Django has two independent routers, and confusing them causes most routing bugs:

- **Django `urls.py`** decides what happens on an HTTP request to the server
- **React Router** runs entirely in the browser via the History API and sends **no request at all**

Two ways a user reaches `/events/some-slug`:

**A — in-app navigation.** Clicks a card. React Router calls `pushState`, swaps the component, fetches from the API. The server never knows. Fast, and the main upside of CSR: slow first load, instant subsequent navigation.

**B — deep link.** Pastes the URL, refreshes, or clicks a link from a chat. The browser sends a real `GET /events/some-slug`. Django knows nothing about that path — it exists only in React Router. Without a catch-all it returns 404.

Hence the catch-all: any unknown path returns the same `index.html`, React boots, reads `window.location.pathname`, and renders accordingly.

Ordering is what makes it work — Django takes the first match top to bottom:

```python
urlpatterns = [
    path(os.environ["ADMIN_URL"], admin.site.urls),
    path("api/", include("api.urls")),
    re_path(r"^(?P<path>.*)$", spa_view),      # must be last
]
```

Corollary: link to server-handled paths (admin, allauth, downloads) with a plain `<a href>`. A React Router `<Link>` is client-side navigation and will 404 inside the SPA.

## Why scrapers see nothing

A link scraper (WhatsApp, Facebook, Discord, Slack) is always scenario B: it requests the URL, reads the HTML, **does not execute JavaScript**, and leaves. On a pure CSR app it sees an empty shell, so a shared link renders as a bare URL with no title or image.

For a community app where sharing is the main distribution channel, that's a measurable difference in click-through.

## The catch-all OG pattern

This gets roughly 90% of SSR's practical benefit in about an hour, with no new service, no Node runtime at the origin, and no change to how React works.

```python
import re
from django.shortcuts import render
from events.models import Event

def spa_view(request, path=""):
    context = {}
    if match := re.match(r"^events/([\w-]+)", path):
        if event := Event.objects.filter(slug=match.group(1)).first():
            context["og"] = {
                "title": event.name,
                "description": event.short_description,
                "image": event.cover_url,
                "url": request.build_absolute_uri(),
            }
    return render(request, "index.html", context)
```

```html
{% if og %}
  <title>{{ og.title }} — Site</title>
  <meta property="og:title" content="{{ og.title }}">
  <meta property="og:description" content="{{ og.description }}">
  <meta property="og:image" content="{{ og.image }}">
  <meta property="og:url" content="{{ og.url }}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
{% endif %}
```

The server stays dumb for humans and smart for robots. React boots exactly as before.

**Safety:** Django templates autoescape, so `{{ og.title }}` inside `content=""` is fine. Building this with an f-string or `mark_safe()` is immediate XSS. `og.image` must come from your own storage, not from a user-supplied URL.

**Verify:** Facebook Sharing Debugger, `curl <url> | grep "og:"`, and send yourself the link in a messenger.

## When SSR is actually the answer

Only when the app needs indexed public content at scale, or when LCP on the first paint is a business problem across the whole site — not for link previews alone.

Understand the tradeoff before recommending it: `renderToString` is synchronous CPU work (roughly 5–50 ms per page), so SSR **reduces** origin throughput. It's paid for by better LCP, not better capacity. Rendered HTML can be edge-cached, and that's what makes SSR viable at scale; SSG/ISR is better still for content that changes hourly rather than per request.

SSR also requires running React on the server, which means a Node runtime. Django cannot server-render React; the realistic options are Next.js in front of Django-as-API, or staying with CSR.

## Metrics vocabulary

- **TTFB** — first byte arrives. Measures server and network, not what the user sees.
- **FCP** — first content painted. End of the blank screen.
- **LCP** — largest above-the-fold element painted. This is the Core Web Vitals one; under 2.5 s is "good".

A CSR app commonly has excellent TTFB and poor LCP. Reporting TTFB as evidence of speed is a common mistake.
