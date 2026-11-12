"""Dashboard SLA figures: open requests already past their SLA count as late."""

from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from api_core.administration.analytics import _lifecycle_bucket, _track_sla

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


class TrackSlaTests(SimpleTestCase):
    def track(self, rows):
        lc = _lifecycle_bucket()
        for hours_ago, status, minutes, sla_hours in rows:
            _track_sla(
                lc, NOW - timedelta(hours=hours_ago), status, minutes, sla_hours, NOW
            )
        return lc

    def test_open_overdue_requests_lower_the_on_time_rate(self):
        lc = self.track(
            [
                (100, "COMPLETED", 60, 24),  # finished in 1 h: on time
                (100, "IN_PROGRESS", None, 24),  # open 100 h, SLA 24 h: late
                (2, "PENDING_APPROVAL", None, 24),  # open 2 h: no verdict yet
            ]
        )
        self.assertEqual(
            (lc["on_time"], lc["evaluated"], lc["overdue_open"]), (1, 2, 1)
        )
        self.assertEqual(lc["durations"], [60.0])

    def test_late_completion_and_closed_without_completion(self):
        lc = self.track(
            [
                (100, "COMPLETED", 30 * 60, 24),  # 30 h against 24 h: late
                (100, "REJECTED", None, 24),  # closed, no completion time
            ]
        )
        self.assertEqual(
            (lc["on_time"], lc["evaluated"], lc["overdue_open"]), (0, 1, 0)
        )

    def test_nothing_due_yet_leaves_no_verdict(self):
        lc = self.track([(1, "PENDING_APPROVAL", None, 24)])
        self.assertEqual(lc["evaluated"], 0)
