"""Account ↔ leaderboard-player linking: the matching logic and the admin tool."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts import matching
from accounts.models import Profile
from leaderboard.cache_config import CACHE_KEY_LEADERBOARD_TOTAL
from leaderboard.models import User as LeaderboardUser

User = get_user_model()

_next_number = iter(range(100_000_001, 100_001_000))


def make_player(name):
    return LeaderboardUser.objects.create(number=next(_next_number), name=name)


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

    def test_claimed_players_are_not_offered(self):
        claimed = make_player("Jan Novák")
        make_account("owner", linked=claimed)
        self.assertNotIn(claimed, matching.unlinked_players())

    def test_linked_accounts_are_not_listed(self):
        player = make_player("Jan Novák")
        linked = make_account("linked", linked=player)
        unlinked = make_account("unlinked")
        accounts = list(matching.unlinked_accounts())
        self.assertIn(unlinked, accounts)
        self.assertNotIn(linked, accounts)

    def test_account_without_a_profile_counts_as_unlinked(self):
        account = make_account("noprofile")
        self.assertFalse(Profile.objects.filter(user=account).exists())
        self.assertIn(account, matching.unlinked_accounts())


class LinkingAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser("root", "r@x.cz", "pw12345!")
        self.client.force_login(self.staff)
        self.player = make_player("Jan Novák")
        self.account = make_account("honza", first_name="Jan", last_name="Novák",
                                    email="jan.novak@gmail.com")

    def test_list_view_shows_an_unlinked_account(self):
        response = self.client.get(reverse("admin:accounts_profile_link_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "honza")
        self.assertContains(response, "Jan Novák")

    def test_detail_view_lists_candidates(self):
        response = self.client.get(
            reverse("admin:accounts_profile_link_detail", args=[self.account.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan Novák")

    def test_post_links_the_account(self):
        self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.account.pk]),
            {"player_id": self.player.pk})
        self.assertEqual(Profile.objects.get(user=self.account).leaderboard_user,
                         self.player)

    def test_linking_evicts_the_leaderboard_cache(self):
        """The board carries profile_username, so a new link changes its output."""
        cache.set(CACHE_KEY_LEADERBOARD_TOTAL, "SENTINEL", 60)
        self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.account.pk]),
            {"player_id": self.player.pk})
        self.assertIsNone(cache.get(CACHE_KEY_LEADERBOARD_TOTAL))

    def test_claiming_an_already_linked_player_is_refused(self):
        """Must be a readable message, not a raw IntegrityError on the OneToOne."""
        make_account("first_owner", linked=self.player)
        response = self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.account.pk]),
            {"player_id": self.player.pk}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "už patří účtu")
        self.assertFalse(
            Profile.objects.filter(user=self.account,
                                   leaderboard_user=self.player).exists())

    def test_unknown_player_id_is_404(self):
        response = self.client.post(
            reverse("admin:accounts_profile_link_detail", args=[self.account.pk]),
            {"player_id": 999999})
        self.assertEqual(response.status_code, 404)

    def test_unlink_clears_the_link(self):
        Profile.objects.create(user=self.account, leaderboard_user=self.player)
        self.client.post(reverse("admin:accounts_profile_unlink", args=[self.account.pk]))
        self.assertIsNone(Profile.objects.get(user=self.account).leaderboard_user)

    def test_unlink_rejects_get(self):
        """Undoing a link changes what a person can see — never on a GET."""
        Profile.objects.create(user=self.account, leaderboard_user=self.player)
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
