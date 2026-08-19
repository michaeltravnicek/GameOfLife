"""Archive player ↔ account matching: the scoring logic and the admin merge tool."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts import matching
from accounts.models import Profile
from leaderboard import merging
from leaderboard.cache_config import season_leaderboard_key
from leaderboard.models import User as LeaderboardUser

User = get_user_model()

def make_player(name):
    return LeaderboardUser.objects.create(name=name)


def make_account(username, first_name="", last_name="", email="", linked=None):
    user = User.objects.create_user(
        username=username, email=email, password="pw12345!",
        first_name=first_name, last_name=last_name,
    )
    if linked is not None:
        Profile.objects.create(user=user, leaderboard_user=linked)
    return user


class FoldTests(TestCase):
    def test_strips_czech_diacritics(self):
        self.assertEqual(matching.fold("Jiří Nováček"), "jiri novacek")

    def test_collapses_whitespace_and_case(self):
        self.assertEqual(matching.fold("  Jan   NOVÁK "), "jan novak")

    def test_handles_none(self):
        self.assertEqual(matching.fold(None), "")


class SimilarityTests(TestCase):
    def test_identical_names_score_one(self):
        self.assertEqual(matching.similarity("Jan Novák", "Jan Novák"), 1.0)

    def test_diacritics_do_not_matter(self):
        self.assertEqual(matching.similarity("Jan Novak", "Jan Novák"), 1.0)

    def test_word_order_does_not_matter(self):
        self.assertEqual(matching.similarity("Novák Jan", "Jan Novák"), 1.0)

    def test_separators_do_not_matter(self):
        """A nickname or e-mail local part runs the words together."""
        self.assertEqual(matching.similarity("jannovak", "Jan Novák"), 1.0)
        self.assertEqual(matching.similarity("jan.novak", "Jan Novák"), 1.0)

    def test_unrelated_names_score_low(self):
        self.assertLess(matching.similarity("Petr Svoboda", "Jan Novák"),
                        matching.MIN_SCORE)

    def test_empty_input_scores_zero(self):
        self.assertEqual(matching.similarity("", "Jan Novák"), 0.0)


class ScoringSignalTests(TestCase):
    def test_email_local_part_can_beat_a_bare_first_name(self):
        """Registration only collects a first name — the e-mail carries the surname."""
        account = make_account("honzik", first_name="Jan", email="jan.novak@gmail.com")
        score, signal = matching.score_player(account, "Jan Novák")
        self.assertEqual(signal, "email")
        self.assertEqual(score, 1.0)

    def test_username_is_used_when_name_and_email_are_useless(self):
        account = make_account("jannovak", email="xyz123@seznam.cz")
        _, signal = matching.score_player(account, "Jan Novák")
        self.assertEqual(signal, "username")

    def test_full_name_wins_when_available(self):
        account = make_account("kdokoli", first_name="Jan", last_name="Novák",
                               email="kdokoli@seznam.cz")
        score, signal = matching.score_player(account, "Jan Novák")
        self.assertEqual((score, signal), (1.0, "name"))


class SuggestionTests(TestCase):
    def test_ranks_the_right_player_first(self):
        make_player("Petr Svoboda")
        target = make_player("Jan Novák")
        account = make_account("j", first_name="Jan", last_name="Novák")
        top = matching.suggest_players(account, LeaderboardUser.objects.all())
        self.assertEqual(top[0]["player"], target)

    def test_noise_is_filtered_out(self):
        make_player("Petr Svoboda")
        account = make_account("j", first_name="Jan", last_name="Novák")
        self.assertEqual(matching.suggest_players(account, LeaderboardUser.objects.all()), [])

    def test_two_identical_names_are_flagged_ambiguous(self):
        """The case that actually gets linked wrong."""
        make_player("Jan Novák")
        make_player("Jan Novák")
        account = make_account("j", first_name="Jan", last_name="Novák")
        top = matching.suggest_players(account, LeaderboardUser.objects.all())
        self.assertEqual(len(top), 2)
        self.assertTrue(top[0]["ambiguous"])

    def test_a_single_clear_match_is_not_ambiguous(self):
        make_player("Jan Novák")
        account = make_account("j", first_name="Jan", last_name="Novák")
        self.assertFalse(matching.suggest_players(
            account, LeaderboardUser.objects.all())[0]["ambiguous"])

    def test_ranks_the_right_account_first(self):
        """The queue runs archive-player → account; same scoring, other way."""
        right = make_account("kdokoliv", first_name="Jan", last_name="Novák",
                             linked=make_player("Jan Novák"))
        wrong = make_account("petr", first_name="Petr", last_name="Svoboda",
                             linked=make_player("Petr Svoboda"))
        ranked = matching.suggest_accounts(
            make_player("Jan Novák"), [wrong, right])
        self.assertEqual(ranked[0]["account"], right)


class MergeQueueTests(TestCase):
    def test_claimed_players_are_not_in_the_archive_queue(self):
        claimed = make_player("Jan Novák")
        make_account("owner", linked=claimed)
        self.assertNotIn(claimed, matching.archive_players())

    def test_merged_players_leave_the_queue(self):
        archive = make_player("Jan Novák")
        target = make_player("Jan Novak")
        make_account("honza", linked=target)
        self.assertIn(archive, matching.archive_players())
        merging.merge_players(archive, target)
        self.assertNotIn(archive, matching.archive_players())

    def test_only_accounts_with_a_player_can_receive_a_merge(self):
        with_player = make_account("linked", linked=make_player("Jan Novák"))
        without = make_account("orphan")
        accounts = list(matching.mergeable_accounts())
        self.assertIn(with_player, accounts)
        self.assertNotIn(without, accounts)

    def test_accounts_without_a_player_are_surfaced_separately(self):
        account = make_account("noprofile")
        self.assertFalse(Profile.objects.filter(user=account).exists())
        self.assertIn(account, matching.accounts_without_player())


class MergeAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser("root", "r@x.cz", "pw12345!")
        self.client.force_login(self.staff)
        # The archive row (Google Forms) and the account that should own it.
        self.archive = make_player("Jan Novák")
        self.own_player = make_player("Jan Novák")
        self.account = make_account("honza", first_name="Jan", last_name="Novák",
                                    email="jan.novak@gmail.com",
                                    linked=self.own_player)

    def _merge(self, follow=False, **extra):
        return self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.archive.pk]),
            {"account_id": self.account.pk, **extra}, follow=follow)

    def test_list_view_shows_an_archive_player(self):
        response = self.client.get(reverse("admin:accounts_profile_link_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan Novák")
        self.assertContains(response, "honza")

    def test_detail_view_lists_candidate_accounts(self):
        response = self.client.get(
            reverse("admin:accounts_profile_link_detail", args=[self.archive.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "honza")

    def test_post_merges_the_archive_player_into_the_account(self):
        self._merge()
        self.archive.refresh_from_db()
        self.assertEqual(self.archive.merged_into, self.own_player)
        self.assertIsNotNone(self.archive.merged_at)
        # The account keeps its own player — the merge never repoints the profile.
        self.assertEqual(Profile.objects.get(user=self.account).leaderboard_user,
                         self.own_player)

    def test_merging_evicts_the_leaderboard_cache(self):
        # The all-time board lives under the per-season family ("all"), which is
        # what the endpoint actually reads. This used to assert on a standalone
        # `leaderboard_data` key that nothing wrote any more, so it passed
        # whether or not the real board was evicted.
        key = season_leaderboard_key("all")
        cache.set(key, "SENTINEL", 60)
        self._merge()
        self.assertIsNone(cache.get(key))

    def test_merged_player_disappears_from_the_queue(self):
        self._merge()
        response = self.client.get(reverse("admin:accounts_profile_link_list"))
        self.assertContains(response, "Nedávno sloučení")

    def test_a_player_that_owns_an_account_is_not_offered_at_all(self):
        """Two gates: it leaves the queue, and the POST 404s even if guessed.

        The service refuses it as well (test_merging.MergeRefusalTests) — this
        one pins that the admin never gets that far, because the failure mode is
        a stranger silently losing their whole history.
        """
        make_account("someone_else", linked=self.archive)
        self.assertNotIn(self.archive, matching.archive_players())
        response = self._merge()
        self.assertEqual(response.status_code, 404)
        self.archive.refresh_from_db()
        self.assertIsNone(self.archive.merged_into)

    def test_unknown_account_id_is_404(self):
        response = self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.archive.pk]),
            {"account_id": 999999})
        self.assertEqual(response.status_code, 404)

    def test_account_without_a_player_cannot_be_a_target(self):
        orphan = make_account("orphan")
        response = self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.archive.pk]),
            {"account_id": orphan.pk})
        self.assertEqual(response.status_code, 404)

    def test_unmerge_puts_the_player_back(self):
        self._merge()
        self.client.post(
            reverse("admin:accounts_profile_unmerge", args=[self.archive.pk]))
        self.archive.refresh_from_db()
        self.assertIsNone(self.archive.merged_into)
        self.assertIn(self.archive, LeaderboardUser.objects.all())

    def test_unmerge_rejects_get(self):
        """Undoing a merge changes the leaderboard — never on a GET."""
        self._merge()
        response = self.client.get(
            reverse("admin:accounts_profile_unmerge", args=[self.archive.pk]))
        self.assertEqual(response.status_code, 404)
        self.archive.refresh_from_db()
        self.assertIsNotNone(self.archive.merged_into)

    def test_unlink_clears_the_link(self):
        self.client.post(reverse("admin:accounts_profile_unlink", args=[self.account.pk]))
        self.assertIsNone(Profile.objects.get(user=self.account).leaderboard_user)

    def test_unlink_rejects_get(self):
        """Undoing a link changes what a person can see — never on a GET."""
        response = self.client.get(
            reverse("admin:accounts_profile_unlink", args=[self.account.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(Profile.objects.get(user=self.account).leaderboard_user)

    def test_non_staff_cannot_reach_the_tool(self):
        self.client.force_login(make_account("nobody"))
        response = self.client.get(reverse("admin:accounts_profile_link_list"))
        self.assertIn(response.status_code, (302, 403))

    def test_staff_without_change_permission_is_denied(self):
        editor = User.objects.create_user("editor", "e@x.cz", "pw12345!", is_staff=True)
        self.client.force_login(editor)
        response = self.client.get(reverse("admin:accounts_profile_link_list"))
        self.assertIn(response.status_code, (302, 403))
