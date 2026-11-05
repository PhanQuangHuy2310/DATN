"""Borrowing rooms / vehicles / equipment (migration 17)."""

from datetime import datetime, time, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.worker import RESOURCE_LABELS
from api_core.workflow import resource_allocation as ra

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


class NeedTests(SimpleTestCase):
    def test_room_window_uses_booking_times_in_vietnam(self):
        need = ra.need_for(
            "ROOM_BOOKING",
            {
                "title": "Họp",
                "room_code": "MR-HCM-02",
                "booking_date": "2026-11-20",
                "start_time": "09:00",
                "end_time": "10:30",
                "attendees_count": 6,
            },
        )
        self.assertEqual(
            (need.kind, need.code, need.quantity), ("FACILITY", "MR-HCM-02", 1)
        )
        self.assertEqual(need.starts_at.astimezone(timezone.utc).hour, 2)
        self.assertEqual(need.headcount, 6)

    def test_equipment_and_vehicle_cover_working_days(self):
        eq = ra.need_for(
            "EQUIPMENT_BORROW",
            {
                "asset_category": "LAPTOP",
                "quantity": 3,
                "start_date": "2026-11-20",
                "end_date": "2026-11-21",
            },
        )
        self.assertEqual((eq.kind, eq.code, eq.quantity), ("ASSET", "LAPTOP", 3))
        self.assertEqual(eq.starts_at.timetz().replace(tzinfo=None), time(8, 0))
        self.assertEqual(eq.ends_at.timetz().replace(tzinfo=None), time(17, 30))
        car = ra.need_for(
            "VEHICLE_BOOKING",
            {
                "vehicle_code": "CAR-HCM-01",
                "start_date": "2026-11-20",
                "end_date": "2026-11-20",
                "passengers": 4,
            },
        )
        self.assertEqual(
            (car.kind, car.code, car.headcount), ("FACILITY", "CAR-HCM-01", 4)
        )

    def test_old_forms_and_other_types_borrow_nothing(self):
        self.assertIsNone(ra.need_for("ROOM_BOOKING", {"room_name": "PHONG_HOP_A_10P"}))
        self.assertIsNone(ra.need_for("WFH_REQ", {"date": "2026-11-20"}))
        backwards = {
            "room_code": "MR-HCM-02",
            "booking_date": "2026-11-20",
            "start_time": "10:00",
            "end_time": "09:00",
        }
        self.assertIsNone(ra.need_for("ROOM_BOOKING", backwards))


class AllocateTests(SimpleTestCase):
    """Allocation talks to the external systems through the API client only."""

    NEED = ra.Need(
        "FACILITY",
        "MR-HCM-02",
        1,
        datetime(2026, 11, 20, 2, tzinfo=timezone.utc),
        datetime(2026, 11, 20, 3, tzinfo=timezone.utc),
        6,
        "Họp",
    )

    def _cursor(self, holders=()):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("staff@eas.com",)
        cursor.fetchall.return_value = list(holders)
        return cursor

    def _allocate(self, cursor):
        return ra.allocate(
            cursor,
            request_id=str(uuid4()),
            requester_id=str(uuid4()),
            need=self.NEED,
            now=NOW,
        )

    def _availability(self, holder):
        return {
            "status": "AVAILABLE",
            "capacity": 8,
            "holders": [{"source_request_id": holder}],
        }

    @patch.object(ra, "is_priority", return_value=False)
    @patch.object(ra.client, "post")
    @patch.object(ra.client, "get")
    def test_employee_cannot_take_a_booked_room(self, get, post, _p):
        get.return_value = self._availability(str(uuid4()))
        with self.assertRaises(ra.ResourceUnavailable):
            self._allocate(self._cursor())
        post.assert_not_called()

    @patch.object(ra, "is_priority", return_value=True)
    @patch.object(ra.client, "post")
    @patch.object(ra.client, "get")
    def test_board_never_takes_from_another_board_member(self, get, post, _p):
        holder = str(uuid4())
        get.return_value = self._availability(holder)
        cursor = self._cursor([(holder, "COMPLETED", True)])
        with (
            patch.object(ra, "preempt") as preempt,
            self.assertRaises(ra.ResourceUnavailable),
        ):
            self._allocate(cursor)
        preempt.assert_not_called()

    @patch.object(ra, "is_priority", return_value=True)
    @patch.object(ra.client, "post")
    @patch.object(ra.client, "get")
    def test_board_takes_back_employee_booking(self, get, post, _p):
        holder = str(uuid4())
        get.return_value = self._availability(holder)
        post.return_value = {"status": "ALLOCATED", "items": ["MR-HCM-02"]}
        cursor = self._cursor([(holder, "COMPLETED", False)])
        with patch.object(ra, "preempt", return_value="EAS-1") as preempt:
            held = self._allocate(cursor)
        self.assertEqual(preempt.call_args.kwargs["victim_id"], holder)
        self.assertEqual(held["preempted_requests"], ["EAS-1"])
        path, body = post.call_args.args[1], post.call_args.args[2]
        self.assertEqual(path, "facilities/reservations")
        self.assertIn("source_request_id", body)

    @patch.object(ra.client, "post")
    def test_handed_over_request_is_not_preempted(self, post):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("EAS-1", "WAITING_FOR_ACCEPTANCE", None)
        with self.assertRaises(ra.ResourceUnavailable):
            ra.preempt(
                cursor,
                victim_id=str(uuid4()),
                by_request_id=str(uuid4()),
                system="facilities",
                now=NOW,
            )
        post.assert_not_called()

    @patch("api_core.workflow.service._append_request_audit")
    @patch.object(ra.client, "post", return_value={"released": ["MR-HCM-02"]})
    def test_preempt_cancels_via_api_rejects_and_notifies(self, post, audit):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("EAS-1", "COMPLETED", str(uuid4()))
        victim = str(uuid4())
        ra.preempt(
            cursor,
            victim_id=victim,
            by_request_id=str(uuid4()),
            system="facilities",
            now=NOW,
        )
        self.assertEqual(
            post.call_args.args[1:],
            ("allocations/cancel", {"source_request_id": victim}),
        )
        sql = [c.args[0] for c in cursor.execute.call_args_list]
        flag = next(i for i, s in enumerate(sql) if "preempt_request_id', %s" in s)
        update = next(i for i, s in enumerate(sql) if "status = 'REJECTED'" in s)
        self.assertLess(flag, update)
        self.assertIn("completed_at = NULL", sql[update])
        self.assertTrue(all("mock_" not in s for s in sql))
        self.assertEqual(audit.call_args.kwargs["action"], "RESOURCE_PREEMPTED")


class NoDirectMockAccessTests(SimpleTestCase):
    def test_eas_code_never_queries_mock_schemas(self):
        """Only the Mock Systems service (api_core/mock_sources) touches mock_*."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        pattern = re.compile(
            r"\bmock_(hr|assets|facilities|crm|procurement|it|finance|travel)\."
        )
        offenders = [
            str(p.relative_to(root))
            for p in root.rglob("*.py")
            if "tests" not in p.parts
            and "mock_sources" not in p.parts
            and p.name != "health_views.py"
            and pattern.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])


class NotificationLabelTests(SimpleTestCase):
    def test_employee_is_told_why(self):
        self.assertIn("Ban Giám đốc", RESOURCE_LABELS["RESOURCE_PREEMPTED"])
        self.assertIn("từ chối tự động", RESOURCE_LABELS["RESOURCE_UNAVAILABLE"])


class IdempotencyCleanupTests(SimpleTestCase):
    def test_clears_expired_bodies_then_deletes_tombstones(self):
        from api_core import worker

        cursor = MagicMock()
        cursor.rowcount = 2
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with (
            patch.object(worker, "connection", conn),
            patch.object(worker, "transaction", MagicMock()),
        ):
            self.assertEqual(worker.process_idempotency_cleanup(batch_size=10), 4)
        update, delete = (c.args[0] for c in cursor.execute.call_args_list)
        self.assertIn("SET response_body = NULL", update)
        self.assertIn("expires_at < clock_timestamp()", update)
        self.assertIn("DELETE FROM eas.idempotency_record", delete)
        self.assertIn("tombstone_until < clock_timestamp()", delete)


class PathEncodingTests(SimpleTestCase):
    def test_code_cannot_escape_its_path_segment(self):
        need = ra.Need("FACILITY", "../hr/employees?x=", 1, NOW, NOW, None, "t")
        with patch.object(ra.client, "get", return_value={}) as get:
            need.availability()
        self.assertEqual(
            get.call_args.args[1],
            "facilities/resources/..%2Fhr%2Femployees%3Fx%3D/availability",
        )
