from datetime import date

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from leaderboard.admin import SeasonAdmin
from leaderboard.models import Season


class SeasonAdminActivationTests(TestCase):
    """Activating a season via the admin must deactivate the others.

    Guards the season_single_active DB constraint: without SeasonAdmin.save_model
    deactivating the rest first, a manual activation would raise IntegrityError.
    """

    def setUp(self):
        self.admin = SeasonAdmin(Season, AdminSite())
        self.old = Season.objects.create(
            name="2024", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
            is_active=True,
        )

    def _save(self, obj):
        self.admin.save_model(request=None, obj=obj, form=None, change=bool(obj.pk))

    def test_activating_new_season_deactivates_previous(self):
        new = Season(name="2025", start_date=date(2025, 1, 1),
                     end_date=date(2025, 12, 31), is_active=True)
        self._save(new)
        self.assertEqual(Season.objects.filter(is_active=True).count(), 1)
        self.old.refresh_from_db()
        self.assertFalse(self.old.is_active)
        self.assertTrue(Season.objects.get(name="2025").is_active)

    def test_saving_inactive_season_leaves_active_one_untouched(self):
        new = Season(name="2025", start_date=date(2025, 1, 1),
                     end_date=date(2025, 12, 31), is_active=False)
        self._save(new)
        self.old.refresh_from_db()
        self.assertTrue(self.old.is_active)
