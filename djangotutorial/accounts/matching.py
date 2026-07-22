"""Suggest which leaderboard player an account belongs to.

Historically the link was exact: registration asked for a phone number and
`LeaderboardUser.number` matched it. Once the number goes away there is no exact
key left, so linking becomes a judgement call -- and judgement calls belong to a
human. Nothing here ever writes: it ranks candidates and explains why, the admin
decides.

Two things make this harder than a plain name comparison:

* Registration only collects `first_name` (see accounts.forms), while a player's
  name came from the Google Form's "Jméno a příjmení". So half the time we are
  matching "Jan" against "Jan Novák", which fits fifteen people.
* Czech diacritics. Folding them is worth more than any clever algorithm --
  without it "Novák" and "Novak" score as different people.

So we compare three signals (name, e-mail local part, nickname) and report which
one fired, because "matched on e-mail 92%" and "matched on first name 60%" are
very different evidence for the person clicking Confirm.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Below this a candidate is noise, not a suggestion.
MIN_SCORE = 0.45
# When the top two are this close, the admin is told to look twice.
AMBIGUOUS_MARGIN = 0.08

SIGNAL_LABELS = {
    "name": "jméno",
    "email": "e-mail",
    "username": "přezdívka",
}


def fold(text):
    """Lowercase, strip diacritics, collapse whitespace: 'Jiří  Novák' -> 'jiri novak'."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_marks).strip().lower()


def tokens(text):
    """Folded alphanumeric words: 'jan.novak99' -> ['jan', 'novak99']."""
    return [t for t in re.split(r"[^a-z0-9]+", fold(text)) if t]


def similarity(left, right):
    """0..1 name similarity, insensitive to word order and separators.

    Sorting the tokens makes "Novák Jan" match "Jan Novák"; also comparing them
    joined makes "jannovak" (a nickname or e-mail local part) match "Jan Novák".
    """
    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    spaced = SequenceMatcher(
        None, " ".join(sorted(left_tokens)), " ".join(sorted(right_tokens))
    ).ratio()
    joined = SequenceMatcher(
        None, "".join(sorted(left_tokens)), "".join(sorted(right_tokens))
    ).ratio()
    return max(spaced, joined)


def account_signals(user):
    """The comparable strings an account carries, best evidence first."""
    return {
        "name": f"{user.first_name} {user.last_name}".strip(),
        # Local part only: the domain is the same for everyone and would inflate
        # every score. "jan.novak@gmail.com" -> "jan.novak".
        "email": (user.email or "").split("@")[0],
        "username": user.username or "",
    }


def score_player(user, player_name):
    """Best (score, signal) for this account against one player name."""
    best_score, best_signal = 0.0, None
    for signal, value in account_signals(user).items():
        if not value:
            continue
        current = similarity(value, player_name)
        if current > best_score:
            best_score, best_signal = current, signal
    return best_score, best_signal


def suggest_players(user, players, limit=5):
    """Rank `players` as link candidates for `user`. Writes nothing.

    Returns dicts of ``{player, score, signal, signal_label, ambiguous}``, best
    first. `ambiguous` is set on the whole result when the top two are within
    AMBIGUOUS_MARGIN -- that is exactly the case a tired admin gets wrong.
    """
    scored = []
    for player in players:
        value, signal = score_player(user, player.name)
        if value >= MIN_SCORE:
            scored.append({
                "player": player,
                "score": value,
                # Templates can't do arithmetic; hand them the display value.
                "percent": round(value * 100),
                "signal": signal,
                "signal_label": SIGNAL_LABELS.get(signal, signal),
            })
    scored.sort(key=lambda candidate: -candidate["score"])
    top = scored[:limit]
    ambiguous = len(top) > 1 and (top[0]["score"] - top[1]["score"]) < AMBIGUOUS_MARGIN
    for candidate in top:
        candidate["ambiguous"] = ambiguous
    return top


def unlinked_players():
    """Leaderboard players that no account has claimed yet."""
    from leaderboard.models import User as LeaderboardUser

    return LeaderboardUser.objects.filter(profile__isnull=True)


def unlinked_accounts():
    """Accounts with no leaderboard player attached (no Profile counts too)."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    return (
        get_user_model().objects
        .filter(Q(profile__isnull=True) | Q(profile__leaderboard_user__isnull=True))
        .order_by("-date_joined")
    )
