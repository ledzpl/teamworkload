from __future__ import annotations

import unittest

from workload_analytics.dashboard.filters import normalize_developer_selection


class DashboardFiltersTest(unittest.TestCase):
    def test_normalize_developer_selection_treats_all_team_as_no_filter(self) -> None:
        self.assertIsNone(normalize_developer_selection("All team"))


if __name__ == "__main__":
    unittest.main()
