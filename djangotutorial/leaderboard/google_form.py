"""Read a Google Form's questions, and post answers back to it.

Why this exists: a Google Form embedded in an iframe is cross-origin, so its
inputs cannot be styled — the site's CSS stops at the frame border. To render
the questions with our own inputs we need the question list ourselves, and to
keep responses flowing into the same spreadsheet we have to submit back to
Google.

Neither half is an official API. Google publishes no endpoint for reading a
public form's structure or for submitting to one programmatically; both are
read off the public respondent page. What that buys is worth the risk — no
per-event setup, and editing the form in Google updates our page by itself —
but the risk is real, so:

  * every parse failure returns None rather than raising, and the caller falls
    back to the plain iframe embed. A form that renders Google-styled beats a
    page that 500s.
  * anything we don't fully understand (multi-page forms, unknown question
    types) counts as a failure. Dropping a question silently would post an
    incomplete response and nobody would notice.
  * submissions that Google rejects are reported to the caller, which keeps the
    answers rather than losing them.
"""
from __future__ import annotations

import json
import logging
import re

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Google is a third party on the far side of the internet: never let one of its
# slow days park a gunicorn worker.
TIMEOUT = 10
SCHEMA_TTL = 60 * 60

_FORM_HOSTS = {"docs.google.com", "forms.gle"}

# The respondent page carries the whole form definition in one undocumented
# JSON blob. Everything below is read out of it positionally.
_DATA_RE = re.compile(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.*?])\s*;\s*</script>", re.S)

# Item shape: [id, title, description, type, entries...]
_I_TITLE, _I_HELP, _I_TYPE, _I_ENTRIES = 1, 2, 3, 4
# Entry shape: [entry_id, options, required, ...]
_E_ID, _E_OPTIONS, _E_REQUIRED = 0, 1, 2

# Google's question-type enum → what our renderer needs to draw.
_TYPES = {
    0: "short_text",
    1: "long_text",
    2: "radio",
    3: "select",
    4: "checkboxes",
    5: "scale",
    9: "date",
    10: "time",
    18: "scale",
}
# Layout-only items: no answer, safe to skip.
_DECORATIVE = {6, 11, 13}
# A page break means the form is paginated, and a paginated form needs a
# pageHistory field on submit that we do not model. Bail out to the embed.
_PAGE_BREAK = 8


def _extract_form_id(url: str) -> str | None:
    """The responder id from a /forms/d/e/<id>/ URL, else the file id."""
    match = re.search(r"/forms/d/(?:e/)?([^/?#]+)", url)
    return match.group(1) if match else None


def _parse_options(raw) -> list[str]:
    # Each option is itself a list whose first element is the label.
    return [str(o[0]) for o in raw or [] if isinstance(o, list) and o and o[0] is not None]


def _parse_items(items) -> list[dict] | None:
    fields = []
    for item in items:
        try:
            item_type = item[_I_TYPE]
        except (IndexError, TypeError):
            return None

        if item_type == _PAGE_BREAK:
            logger.info("google_form: multi-page form, falling back to embed")
            return None
        if item_type in _DECORATIVE:
            continue

        entries = item[_I_ENTRIES] if len(item) > _I_ENTRIES else None
        if not entries:
            continue  # section headers and other answerless items

        kind = _TYPES.get(item_type)
        if kind is None:
            logger.info("google_form: unsupported question type %s", item_type)
            return None
        # Grid questions carry several entries under one title; we don't render
        # them, and answering only the first would post a partial response.
        if len(entries) > 1:
            logger.info("google_form: grid question, falling back to embed")
            return None

        entry = entries[0]
        entry_id = entry[_E_ID]
        if entry_id is None:
            return None
        options = _parse_options(entry[_E_OPTIONS] if len(entry) > _E_OPTIONS else None)
        if kind in {"radio", "select", "checkboxes", "scale"} and not options:
            return None

        fields.append({
            "entry_id": f"entry.{entry_id}",
            "label": item[_I_TITLE] or "",
            "help": (item[_I_HELP] if len(item) > _I_HELP else "") or "",
            "type": kind,
            "required": bool(entry[_E_REQUIRED]) if len(entry) > _E_REQUIRED else False,
            "options": options,
        })
    return fields


def parse_schema(html: str) -> dict | None:
    """Pull `{title, fields}` out of a respondent page. None if unparseable."""
    match = _DATA_RE.search(html)
    if not match:
        logger.warning("google_form: FB_PUBLIC_LOAD_DATA_ not found — page format changed?")
        return None
    try:
        data = json.loads(match.group(1))
        items = data[1][1]
        title = data[1][8] if len(data[1]) > 8 else ""
    except (ValueError, IndexError, TypeError):
        logger.warning("google_form: blob did not have the expected shape")
        return None

    fields = _parse_items(items)
    if not fields:
        return None
    return {"title": title or "", "fields": fields}


def fetch_schema(survey_url: str, *, use_cache: bool = True) -> dict | None:
    """Fetch + parse a form. Cached, because every visitor would otherwise
    make us fetch a page from Google that changes maybe twice a year."""
    if not survey_url:
        return None
    form_id = _extract_form_id(survey_url)
    if not form_id:
        return None

    key = f"gform_schema:{form_id}"
    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            # False is the cached "this one doesn't parse" marker — without it
            # an unparseable form re-fetches on every single page view.
            return cached or None

    # Rewrite to the respondent view: admins paste the /edit URL, and Google
    # redirects /forms/d/<file-id>/viewform to the public /forms/d/e/<id>/ one.
    prefix = "e/" if "/forms/d/e/" in survey_url else ""
    url = f"https://docs.google.com/forms/d/{prefix}{form_id}/viewform"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("google_form: fetch failed for %s (%s)", url, exc)
        return None

    schema = parse_schema(resp.text)
    if schema is not None:
        # formResponse only accepts the responder id, which the redirect above
        # is how we learn — take it off the URL we actually landed on.
        schema["form_id"] = _extract_form_id(resp.url) or form_id
    cache.set(key, schema or False, SCHEMA_TTL)
    return schema


def invalidate_schema(survey_url: str) -> None:
    form_id = _extract_form_id(survey_url or "")
    if form_id:
        cache.delete(f"gform_schema:{form_id}")


def submit(form_id: str, answers: dict[str, list[str]]) -> bool:
    """POST answers to the form. True when Google accepted them.

    Checkbox questions send one repeated parameter per ticked option, which is
    why every value is a list.
    """
    url = f"https://docs.google.com/forms/d/e/{form_id}/formResponse"
    try:
        resp = requests.post(url, data=answers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("google_form: submit failed (%s)", exc)
        return False
    # Google answers a good submission with the confirmation page (200); a
    # rejected one comes back 400, and a form closed to responses 200s with a
    # different page — which we cannot tell apart, so 2xx is the best signal.
    if not resp.ok:
        logger.warning("google_form: submit rejected with HTTP %s", resp.status_code)
    return resp.ok
