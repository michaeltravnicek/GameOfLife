# GameOfYolo

## Project context (auto-read by Claude Code)

Design: warm indigo (rgba(71, 81, 133)) + cream background (rgba(245, 240, 232)) + minimal accents.
Visual references: design_ref/ folder with Instagram screenshots.

Database: read models.py fully before making any changes.

Auth flow: phone number OR username login, integrated with existing User model.
Critical: do NOT drop existing users — migrate with care.

Language: Czech throughout.
Backend: Django, server-rendered.
Frontend: Tailwind CSS + Alpine.js (NO SPA, NO frontend framework overhead).

## Design requirements
- Event detail: photo hero (400px) + cream card info below
- Homepage: hero + 3 upcoming events cards + leaderboard teaser
- Leaderboard: ranked list, profile links work only if user has account
- Profile page: overview + tabs (upcoming + past events) with feedback
- Auth forms: centered cream cards, indigo headings, clean inputs

## When ready
Before pasting the main prompt, Claude Code should confirm:
"I understand the color palette (indigo + cream), the event detail layout (photo + card),
the existing database structure, and the auth integration approach. Ready to code."

Only then paste the main prompt from GAMEOFYOLO_CLAUDE_CODE_FINAL_PROMPT.md.