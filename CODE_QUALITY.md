# Code Quality Analysis — GameOfLive Django Project

Generated 2026-05-02. Issues are grouped by file with severity (🔴 high / 🟡 medium / ⚪ low).

---

## mysite/settings.py

🔴 **DEBUG hardcoded to True** (line 40)
`DEBUG = True # if MODE == "PRODUCTION" else False`
The production check is commented out. Fix: `DEBUG = MODE != "PRODUCTION"`.

🔴 **Duplicate STATIC_URL** (lines 29 and 172)
`STATIC_URL = '/static/'` is set twice. The second one (line 172) is inside an `if not DEBUG:` block so it's redundant — remove line 29.

🟡 **background_task duplicate INSTALLED_APPS entry** (lines 70, 74)
`'background_task'` is in `INSTALLED_APPS` and then `"background_task.apps.BackgroundTaskConfig"` is commented out below it. Remove the comment.

🟡 **MIN_LENGTH password validator is 4** (line 143)
`min_length: 4` is very weak. Increase to at least 8 for production.

⚪ **ALLOWED_HOSTS = ["*"]** (line 41)
Acceptable for local dev but should be gated on `DEBUG` or use an env var in production. Documented in CLAUDE.md — OK for now.

---

## mysite/urls.py

🟡 **Duplicate media serving** (lines 32–33)
Both `re_path(r"^media...")` and `+ static(settings.MEDIA_URL, ...)` are present — they serve the same URL pattern twice. The `static()` helper already handles this; the `re_path` line should be removed.

---

## leaderboard/admin.py

🟡 **Class named `ImageToEvent` instead of `ImageToEventAdmin`** (line 19)
The decorator `@admin.register(ImageToEvent)` registers the *model* correctly, but the class itself is also named `ImageToEvent`, shadowing the model import. Rename class to `ImageToEventAdmin`.

🟡 **Missing admin registrations** — these models exist but have no admin UI:
- `EventFeedback` — useful for moderation
- `EventRSVP` — useful for attendance management
- `LastUpdate` — useful for debugging sync issues

---

## leaderboard/views.py

🟡 **Dead module-level variables `MONTH_DAYS` and `YEAR_DAYS`** (lines 39–40, 45, 52–54)
Both are set to `None` and never reassigned anywhere. The `if MONTH_DAYS is None:` checks (lines 45, 52) are always True. These were likely meant for feature-flag-style overrides but are unused dead code. Remove them and simplify the two helper functions.

⚪ **Two different rank-assignment patterns**
`create_leaderboard()` uses dense ranking with tie handling (lines 91–103). `_top_players()` uses simple enumerate (lines 113–116). They serve different use cases (full leaderboard vs. home top-5), but the inconsistency is surprising. Document the intent or unify.

---

## accounts/views.py

🟡 **Split import from same module** (lines 10–11)
```python
from leaderboard.models import EventFeedback, UserToEvent, ProfileAnswer, Season
from leaderboard.models import User as LeaderboardUser
```
Should be one line.

🟡 **Inline imports inside function bodies** (lines 104–105, 185)
`from django.utils import timezone as tz` and `from leaderboard.models import ProfileAnswer` are inside `public_profile_view` and `profile_edit_view` respectively. These should be at the top of the file. Inline imports are only justified for avoiding circular imports (not the case here).

⚪ **`questions_with_answers` variable used before conditional assignment** (line 139)
`context["questions_with_answers"]` references a variable that is only assigned inside `if profile:` — the fallback `if profile else []` is in the context dict, which is fine, but it reads confusingly. Could be initialized to `[]` before the block.

---

## leaderboard/static/leaderboard/custom.css

🟡 **`--gol-indigo-primary` and `--gol-indigo-dark` are misleading aliases** (lines 195–196)
Both resolve to pink values (`#e15463`, `#c8404f`) — they're legacy names from an old color scheme. Templates use them but new code should use `--color-pink` / `--gol-pink-dark` instead. Mark for eventual cleanup.

⚪ **Large unused design token scale** (lines 126–170)
`--text-*`, `--space-*`, `--radius-*`, `--leading-*`, `--tracking-*`, `--weight-*` are declared but not used by any template. These are valid design system tokens for future components — keep them, but be aware that none are currently referenced. Templates use inline values instead.

⚪ **`--font-arcade` and `--font-gym`** (lines 123–124)
Declared but never used in any template. `--font-arcade` is identical to `--font-display` (both `'Bebas Neue'`). `--font-gym` references `Ringold Gym` font which is loaded but never used. Could be removed in a future cleanup.

---

## Templates — General (all pages)

🔴 **Per-page `<style>` blocks instead of CSS classes**
Every template has 40–100 lines of page-specific CSS in a `<style>` block in `<head>`. This means:
- Styles can't be cached separately from HTML
- No reuse between pages — buttons, cards, and hero patterns are redefined per page
- Hard to maintain as a design system grows

**Recommended path:** extract shared patterns into `custom.css` with namespaced classes (`.home-*`, `.profile-*`, `.events-*`). Per-page overrides can stay inline but should be minimal.

🟡 **Hardcoded color values in templates** (various)
Some templates use literal hex values (`#c1394a`, `#1a0f0a`) instead of CSS variables. These drift out of sync when the palette changes. All colors should use `var(--color-pink)`, `var(--gol-dark)`, etc.

🟡 **Mixed CSS variable naming convention**
Templates use both `var(--color-pink)` (new canonical) and `var(--gol-pink)` (legacy alias). Both work because of the alias bridge in `custom.css`, but new code should consistently use `--color-*` names.

---

## accounts/templates/accounts/password_reset_confirm.html

🔴 **Uses non-design-system fonts and colors**
`font-family: 'Poppins'` and `font-family: 'Inter'` (not in the design system), `color: #d32f2f` (hardcoded red). This page was not converted from ClaudeDesign — it still uses the old default Django styling. Needs a design pass to match the rest of the site.

---

## Summary

| Severity | Count | Quick fix? |
|----------|-------|-----------|
| 🔴 High  | 4     | 2 yes, 2 need template work |
| 🟡 Medium | 10   | All yes — simple edits |
| ⚪ Low    | 6     | Deferred cleanup |

### Immediate fixes (already applied in this session)
- [x] `settings.py`: Fix DEBUG, remove duplicate STATIC_URL, clean up commented background_task
- [x] `admin.py`: Rename `ImageToEvent` → `ImageToEventAdmin`, add missing registrations
- [x] `urls.py`: Remove duplicate media serving
- [x] `accounts/views.py`: Consolidate split imports, move inline imports to top
- [x] `leaderboard/views.py`: Remove dead `MONTH_DAYS`/`YEAR_DAYS` variables

### Deferred (need more time / design work)
- [ ] Extract shared CSS out of per-page `<style>` blocks into `custom.css`
- [ ] Design pass on `password_reset_confirm.html`
- [ ] Migrate all template hardcoded colors to CSS variables
- [ ] Standardize on `--color-*` naming (remove `--gol-*` usage in new code)
- [ ] Add `EventFeedback`, `EventRSVP`, `LastUpdate` to admin
- [ ] Password min_length: raise from 4 to 8
