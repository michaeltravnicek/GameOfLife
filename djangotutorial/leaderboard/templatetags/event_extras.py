from django import template
import json

register = template.Library()


CATEGORY_KEYWORDS = [
    ("karaoke", "karaoke", "Karaoke"),
    ("ice",     "ice",     "Bruslení"),
    ("skat",    "ice",     "Bruslení"),
    ("brusl",   "ice",     "Bruslení"),
    ("run",     "running", "Běh"),
    ("běh",     "running", "Běh"),
    ("míle",    "running", "Běh"),
    ("jump",    "running", "Běh"),
    ("naha",    "running", "Běh"),
    ("nahá",    "running", "Běh"),
    ("book",    "books",   "Knihy"),
    ("board",   "games",   "Hry"),
    ("ghetti",  "games",   "Hry"),
    ("dance",   "dance",   "Tanec"),
    ("tanec",   "dance",   "Tanec"),
    ("palermo", "games",   "Hry"),
    ("sleep",   "night",   "Sleepover"),
    ("night",   "night",   "Noc"),
    ("wet",     "games",   "Hry"),
    ("wall",    "games",   "Hry"),
]


def _match(event_name: str):
    if not event_name:
        return ("default", "Akce")
    name = event_name.lower()
    for keyword, key, label in CATEGORY_KEYWORDS:
        if keyword in name:
            return (key, label)
    return ("default", "Akce")


@register.filter
def event_category(event):
    name = getattr(event, "name", "") if not isinstance(event, str) else event
    return _match(name)[0]


@register.filter
def event_category_label(event):
    name = getattr(event, "name", "") if not isinstance(event, str) else event
    return _match(name)[1]


@register.filter
def as_json(value):
    messages = [str(msg) for msg in value] if hasattr(value, '__iter__') else [str(value)]
    return json.dumps(messages)


@register.filter
def startswith(value, prefix):
    return str(value).startswith(prefix)
