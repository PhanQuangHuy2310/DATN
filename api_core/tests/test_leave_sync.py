from datetime import time

from django.test import SimpleTestCase

from api_core.workflow.leave_sync import leave_record


class LeaveRecordTests(SimpleTestCase):
    def test_leave_and_trip_cover_whole_days(self):
        kind, start, end = leave_record(
            "LEAVE", {"start_date": "2026-11-05", "end_date": "2026-11-06"}
        )
        self.assertEqual(kind, "PAID_LEAVE")
        self.assertEqual(
            (start.date().isoformat(), start.time()), ("2026-11-05", time(0, 0))
        )
        self.assertEqual(
            (end.date().isoformat(), end.time()), ("2026-11-06", time(23, 59, 59))
        )
        kind, _, _ = leave_record(
            "BUSINESS_TRIP", {"start_date": "2026-11-05", "end_date": "2026-11-05"}
        )
        self.assertEqual(kind, "BUSINESS_TRIP")

    def test_attendance_adjustment_half_day(self):
        kind, start, end = leave_record(
            "ATTENDANCE_ADJUSTMENT",
            {"work_date": "2026-11-05", "change_type": "Đi muộn"},
        )
        self.assertEqual(
            (kind, start.time(), end.time()), ("LATE_IN", time(8, 0), time(12, 0))
        )
        self.assertIsNone(
            leave_record(
                "ATTENDANCE_ADJUSTMENT",
                {"work_date": "2026-11-05", "change_type": "Quên chấm công"},
            )
        )

    def test_invalid_or_unrelated_payloads_are_ignored(self):
        self.assertIsNone(
            leave_record(
                "LEAVE", {"start_date": "2026-11-06", "end_date": "2026-11-05"}
            )
        )
        self.assertIsNone(leave_record("LEAVE", {"start_date": "x"}))
        self.assertIsNone(
            leave_record(
                "IT_SUPPORT", {"start_date": "2026-11-05", "end_date": "2026-11-06"}
            )
        )

    def test_unpaid_leave_is_recorded_as_unpaid(self):
        kind, _, _ = leave_record(
            "LEAVE",
            {
                "start_date": "2026-11-05",
                "end_date": "2026-11-05",
                "leave_kind": "KHONG_LUONG",
            },
        )
        self.assertEqual(kind, "UNPAID_LEAVE")
