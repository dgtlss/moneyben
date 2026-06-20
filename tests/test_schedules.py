from datetime import datetime, timezone
import unittest

from app.trading212 import ScheduleEvent, WorkingSchedule


class ScheduleTests(unittest.TestCase):
    def test_regular_open_schedule_is_tradable(self):
        from app.schedules import is_schedule_open

        schedule = WorkingSchedule(
            id=100,
            exchange_name="NASDAQ",
            events=[
                ScheduleEvent(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc), "OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc), "CLOSE"),
            ],
        )

        self.assertTrue(is_schedule_open(schedule, datetime(2026, 6, 19, 15, 0, tzinfo=timezone.utc), False))

    def test_premarket_requires_extended_hours(self):
        from app.schedules import is_schedule_open

        schedule = WorkingSchedule(
            id=100,
            exchange_name="NASDAQ",
            events=[
                ScheduleEvent(datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc), "PRE_MARKET_OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc), "OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc), "CLOSE"),
            ],
        )
        now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)

        self.assertFalse(is_schedule_open(schedule, now, False))
        self.assertTrue(is_schedule_open(schedule, now, True))

    def test_closed_schedule_is_not_tradable(self):
        from app.schedules import is_schedule_open

        schedule = WorkingSchedule(
            id=100,
            exchange_name="NASDAQ",
            events=[
                ScheduleEvent(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc), "OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc), "CLOSE"),
            ],
        )

        self.assertFalse(is_schedule_open(schedule, datetime(2026, 6, 19, 21, 0, tzinfo=timezone.utc), False))


if __name__ == "__main__":
    unittest.main()
