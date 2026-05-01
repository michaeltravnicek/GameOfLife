
## VISUAL FOUNDATIONS

### Colors
- **White:** `#ffffff`
- **Near-black:** `#1a1a1a`
- **Cream light:** `#fff1d4`
- **Cream lighter:** `#fff4e1`
- **Pink/Coral (primary accent):** `#e15463`
- **Deep purple:** `#2d2a8e` (approx. from textures/screenshots)
- **Dark brown:** `#1a0f0a` (grain texture dark base)
- **Tan/beige:** `#c4a882` (grain texture light base)

### Typography
- **Display/Headlines:** Ringold Sans, Ringold Clarendon, Ringold Gym, Ringold Slab, Ringold Soft (custom paid fonts — NOT on Google Fonts). **Substituted with Bebas Neue** (Google Fonts) for bold condensed headlines.
- **Body/UI:** Helvetica World (commercial) → **Substituted with Barlow** (Google Fonts).
- **Mono:** IBM Plex Mono (available on Google Fonts — exact match).
- Headlines: ALL CAPS, very bold, wide tracking in some contexts.
- Body: Regular weight, generous line-height (~1.6).

### Backgrounds & Textures
- **Grain textures are central to the brand.** Three variants: light (cream/tan), medium purple (deep violet with grain), dark (near-black with grain).
- Sections alternate between grain texture backgrounds.
- Hero sections use photo collages with dark overlay + bold text on top.
- No flat solid-color backgrounds without texture.

### Layout
- Full-bleed sections stacked vertically.
- Max content width ~1200px, centered.
- Alternating section backgrounds: cream → purple → dark → cream.
- Navigation: fixed top bar, semi-transparent or solid dark.

### Buttons
- Pill-shaped (border-radius: 9999px).
- Primary: `#e15463` fill, white text, arrow suffix (→).
- Secondary/outline: dashed border, light text on dark bg.
- Hover: slightly darker fill or slight scale.

### Cards / Frames
- **Dashed border** on cards (white dashed line, 2px, ~12px radius).
- Cards float on grain-textured section backgrounds.
- Event cards: compact, with event name, date, points badge.

### Decorative Elements
- ✦ Sparkle/star glyphs (4-pointed stars) used as ornaments around logo and headings.
- Pink sparkles (#e15463 or bright pink) flank logo and section titles.
- Section titles often have sparkle prefix/suffix: `✦ NADCHÁZEJÍCÍ AKCE ✦`

### Imagery
- Photography: real event photos, warm-toned, candid/energetic.
- Collage grid of event photos used as hero background.
- Dark overlay (~60% opacity) on photo backgrounds for text legibility.
- Grain overlay on all photos/backgrounds for unified texture.

### Iconography
- Minimal icons in the website UI.
- Emoji used in social content / event descriptions.
- No dedicated icon library identified in codebase.
- Navigation and UI use text labels, not icons (except arrows).

### Animations
- Smooth, subtle. No bouncy animations identified.
- Likely CSS transitions on hover states (opacity/color shift).

### Corner Radii
- Cards: ~12px with dashed border.
- Buttons: fully rounded (pill).
- No sharp corners in UI elements.

### Shadows
- Subtle box shadows on cards for elevation.

---

## ICONOGRAPHY

No dedicated icon font or SVG sprite found in the codebase (Django backend only, no frontend static files committed). The brand uses:
- **Sparkle glyphs** (✦, ✧, ★) as decorative marks around headings and logo.
- **Arrow →** as CTA suffix in buttons.
- **Emoji** in event descriptions and social copy (not in web UI).
- For the UI kit, text + arrow patterns are used in place of icon buttons.

**Substitution note:** No icon library detected. No substitution needed for website UI.
