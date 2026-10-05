"""Fold same-person duplicate players into one, through the reversible merge.

The sheets import matches people by e-mail first and by exact name second, so
one human can be two players: the name-only archive row, and a row the import
created from a form that collected the e-mail. Both hold the same attendance
and sit on the leaderboard twice.

Two rows are treated as one person only when that is near certain:

* same name after folding case, accents, whitespace and word order, and one
  history contains the other; or
* same first name and surname initial, the exact same history of at least two
  events, and exactly one of the two rows carries an e-mail (the sync's mark).

A player that belongs to an account is never touched -- that is an admin
decision (`accounts.matching`) -- and neither is a pair that both carry an
e-mail, because two addresses are two people. Everything else that
looks alike is listed as a candidate for the admin merge, not merged.

Idempotent and dry-run by default; `--apply` merges. Each merge is
`merging.merge_players`, so `unmerge_players` takes any of them back.
"""
import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand


def _tokens(name):
    folded = unicodedata.normalize("NFKD", (name or "").casefold())
    return "".join(c for c in folded if not unicodedata.combining(c)).split()


def _name_keys(name):
    """Grouping keys: the full name in any word order, and first name + surname initial."""
    t = _tokens(name)
    if len(t) < 2:
        return ()
    return (("full",) + tuple(sorted(t)), ("short", t[0], t[-1][:1]))


def _same_person(a, b, history, linked):
    """(target, source) when `a` and `b` are one human, else None."""
    if a.pk in linked or b.pk in linked or (a.email and b.email):
        return None
    ha, hb = history[a.pk], history[b.pk]
    if not ha or not hb:
        return None
    if sorted(_tokens(a.name)) == sorted(_tokens(b.name)):
        if not (ha <= hb or hb <= ha):
            return None
    elif not (ha == hb and len(ha) >= 2 and bool(a.email) != bool(b.email)):
        return None
    # Keep the row holding the e-mail (future sign-ups resolve by it), then the
    # longer history, then the older row.
    return tuple(sorted((a, b), key=lambda p: (not p.email, -len(history[p.pk]), p.pk)))


class Command(BaseCommand):
    help = "Merge players that are the same person stored twice (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Perform the merges instead of only listing them.")

    def handle(self, *args, **options):
        from accounts.models import Profile
        from leaderboard.merging import MergeError, merge_players
        from leaderboard.models import User, UserToEvent

        apply = options["apply"]
        players = list(User.objects.all())
        history = defaultdict(set)
        for uid, eid in UserToEvent.objects.filter(user__in=players).values_list("user_id", "event_id"):
            history[uid].add(eid)
        linked = set(Profile.objects.exclude(leaderboard_user=None)
                     .values_list("leaderboard_user_id", flat=True))

        groups = defaultdict(list)
        for p in players:
            if history[p.pk]:
                for key in _name_keys(p.name):
                    groups[key].append(p)

        gone, merged = set(), 0
        for key in sorted(groups):
            alive = sorted((p for p in groups[key] if p.pk not in gone), key=lambda p: p.pk)
            changed = True
            while changed:
                changed = False
                for i, a in enumerate(alive):
                    for b in alive[i + 1:]:
                        pair = _same_person(a, b, history, linked)
                        if pair is None:
                            continue
                        target, source = pair
                        self.stdout.write(
                            f"{'merge' if apply else 'would merge'} #{source.pk} {source.name!r} "
                            f"-> #{target.pk} {target.name!r} ({len(history[source.pk])} events)")
                        if apply:
                            try:
                                merge_players(source, target, performed_by="dedupe_players",
                                              automatic=True)
                            except MergeError as exc:
                                self.stderr.write(f"  skipped: {exc}")
                                continue
                        history[target.pk] |= history.pop(source.pk)
                        if source.email and not target.email:
                            target.email = source.email
                        gone.add(source.pk)
                        alive.remove(source)
                        merged += 1
                        changed = True
                        break
                    if changed:
                        break

        candidates = set()
        for key, group in groups.items():
            if key[0] != "short":
                continue
            alive = [p for p in group if p.pk not in gone]
            for i, a in enumerate(alive):
                for b in alive[i + 1:]:
                    if history[a.pk] & history[b.pk]:
                        candidates.add((a.pk, b.pk))
                        self.stdout.write(
                            f"candidate (not merged, check in admin): #{a.pk} {a.name!r} / "
                            f"#{b.pk} {b.name!r}")

        verb = "Merged" if apply else "Would merge"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {merged} duplicate player(s); {len(candidates)} candidate pair(s) left for the admin."))
