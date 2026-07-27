"""Sitemaps for the React SPA's public routes.

A client-rendered SPA gives crawlers an empty ``#root`` and no links to follow,
so the sitemap is how the real pages get discovered at all. It lists the URLs a
search engine should index -- the public content pages and every visible event
-- and pairs with mysite.og, which then describes each of those URLs.

Locations are the SPA's own client-side paths (``/events/<slug>`` etc.), not
Django views: Django only serves the shell for them, but a URL in the sitemap is
still a real, crawlable page. Player/profile pages are deliberately left out --
most leaderboard entries are Sheets-synced people who never consented to be
published, so we don't invite a crawler to index thousands of thin, pseudonymous
pages (their link previews stay consent-gated in mysite.og either way).

`protocol = "https"` is set explicitly: behind Cloudflare the request can look
like http internally, and a sitemap of http:// URLs invites duplicate-URL noise.
"""
from django.contrib.sitemaps import Sitemap


class StaticViewSitemap(Sitemap):
    """The public content pages that aren't tied to a single DB row."""

    priority = 0.6
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        # Auth, forms, admin and per-user pages are intentionally absent.
        return ["/", "/events", "/leaderboard", "/galerie", "/o-bodech", "/historie"]

    def location(self, item):
        return item


class EventSitemap(Sitemap):
    """Every event a crawler is allowed to see, newest first."""

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        from leaderboard.models import Event

        return (
            Event.objects
            .filter(visible_to_users=True, slug__isnull=False)
            .only("slug", "updated_at", "date")
            .order_by("-date")
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return f"/events/{obj.slug}"


SITEMAPS = {
    "static": StaticViewSitemap,
    "events": EventSitemap,
}
