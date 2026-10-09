from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from api_core.worker import classify_sla_alert, retry_delay, safe_error_code


class WorkerPolicyTests(SimpleTestCase):
    def test_retry_backoff_is_bounded(self):
        self.assertEqual(retry_delay(1), timedelta(seconds=15))
        self.assertEqual(retry_delay(4), timedelta(seconds=120))
        self.assertEqual(retry_delay(20), timedelta(seconds=300))
        with self.assertRaises(ValueError):
            retry_delay(0)

    def test_error_code_never_leaks_exception_message(self):
        error = RuntimeError("password=do-not-log")
        code = safe_error_code(error)
        self.assertEqual(code, "RUNTIMEERROR")
        self.assertNotIn("password", code.lower())

    def test_sla_boundary_prefers_breach_then_single_reminder_window(self):
        start = datetime(2026, 10, 9, tzinfo=timezone.utc)
        due = start + timedelta(hours=24)
        self.assertIsNone(
            classify_sla_alert(
                started_at=start,
                due_at=due,
                breached_at=None,
                now=start + timedelta(hours=11, minutes=59),
            )
        )
        self.assertEqual(
            classify_sla_alert(
                started_at=start,
                due_at=due,
                breached_at=None,
                now=start + timedelta(hours=12),
            ),
            "REMINDER",
        )
        self.assertEqual(
            classify_sla_alert(started_at=start, due_at=due, breached_at=None, now=due),
            "BREACH",
        )
