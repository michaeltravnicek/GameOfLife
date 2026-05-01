# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A static HTML/CSS/JS design mockup for **Game of Life** ("Život je hra, tak ho hrej") — a Czech-language event/community site. There is no build system, no package manager, no tests, and no backend. Each `*.html` page is a standalone, openable file. Preview by opening files in a browser (or `python3 -m http.server` from the repo root so the shared font / image paths resolve).

UI copy is in **Czech**. Keep that language when editing labels, nav items, and headings unless asked otherwise.

## Architecture

Three things hold the site together across pages:

1. **[colors_and_type.css](colors_and_type.css)** — the single source of truth for design tokens (CSS custom properties on `:root`). Colors, fonts (`Bebas Neue` display / `Barlow` body / `Courier Prime` italic mono), spacing scale, radii, shadows. Every page links this file. **Always reach for these vars before introducing new colors or sizes**; one-off literals will drift the design.

2. **[nav.js](nav.js)** — shared top nav component. A page opts in by:
   ```html
   <script>window.GOL_PAGE = 'events'</script>   <!-- highlights active link -->
   <div id="nav-root"></div>
   <script src="nav.js"></script>
   ```
   Known `GOL_PAGE` keys: `home`, `events`, `gallery`, `leaderboard`, `profile`. The nav injects its own `<style>` block, so per-page CSS for `nav.top` in [index.html](index.html) is legacy/duplicate and should not be edited there — change [nav.js](nav.js) instead.

3. **`localStorage['gol_user']`** — the only "auth" mechanism. Presence of this key flips the nav between guest mode (shows *Start Playing* CTA → `register.html`) and logged-in mode (shows *Eshop* + avatar with initials → `profile.html`). [login.html](login.html) / [register.html](register.html) are the writers; [profile.html](profile.html) likely reads/clears it.

## Pages and their roles

- [index.html](index.html) — landing / hero / events teaser / leaderboard teaser / about
- [events.html](events.html) + [event_detail.html](event_detail.html) — event listing and detail
- [gallery_page.html](gallery_page.html) — gallery (uses photos in [gallery/](gallery/))
- [leaderboard.html](leaderboard.html) — full leaderboard
- [login.html](login.html) / [register.html](register.html) — auth flows (no `GOL_PAGE` set; nav appears in guest state)
- [profile.html](profile.html) — logged-in user page
- [index-print.html](index-print.html) — **standalone** A4-landscape print export. Inlines its own subset of design tokens and does **not** link `colors_and_type.css` or use `nav.js`. If you change the palette in `colors_and_type.css`, mirror the relevant vars in this file by hand.

## Assets

- [logos/](logos/) — brand marks; `GOL_main_logo_pink.png` is the nav logo.
- [assets/](assets/) — grain-texture overlays applied as `background-image` on dark sections (purple/brown/blue/light variants, each with a `*2` higher-density pair). Note: [index.html](index.html:49) references `Grain_texture_medium_purple.png` which is **not** in `assets/` — broken link to be aware of.
- [gallery/](gallery/) — `gal0.jpg`–`gal3.jpg`, used both in the gallery page and as backgrounds (e.g. leaderboard tint in [index.html](index.html)).
- [fonts/](fonts/) — locally hosted `Courier Prime Italic` (Google Fonts is the primary source; this is a fallback declared in `@font-face`).
- [design_ref/](design_ref/) — Figma/PNG reference mockups. Match these when implementing or revising sections; they're the visual spec, not decoration.
- [export/src/](export/src/) — a trimmed deliverable bundle (just `index.html` + `nav.js` + `colors_and_type.css`). Treat this as a build artifact — regenerate by copying from the repo root rather than editing in place.
- [scraps/](scraps/) — sketches/notes, not part of the site.

## Conventions worth keeping

- Per-page CSS lives in a single `<style>` block in the page's `<head>` and is intentionally compact (one selector per line, semicolons hugging properties). Match this style when extending — no separate per-page stylesheets.
- Nav state is hide-on-scroll-down / show-on-scroll-up, implemented in [nav.js](nav.js). Don't duplicate scroll handlers on individual pages.
- `--color-pink` (`#e15463`) is the single accent / hover / CTA color — preserve that role.
