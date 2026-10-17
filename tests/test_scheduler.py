import unittest
from datetime import datetime, timezone

from app.scheduler import next_run_at


class SchedulerTests(unittest.TestCase):
    def test_first_run_uses_today_or_tomorrow(self):
        now = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(
            next_run_at(now, None, 1, 6, 0),
            datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            next_run_at(now, None, 1, 12, 0),
            datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
        )

    def test_interval_days(self):
        now = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)
        last = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)
        self.assertEqual(
            next_run_at(now, last, 7, 6, 0),
            datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc),
        )

    def test_skips_missed_intervals(self):
        now = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)
        last = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        self.assertEqual(
            next_run_at(now, last, 3, 6, 0),
            datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
