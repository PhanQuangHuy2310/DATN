from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow.service import (
    CommandError,
    cancel_request,
    decide_acceptance,
    decide_approval,
    start_execution,
    submit_execution,
    submit_request,
)


class WorkflowCommandBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()),
            email="actor@eas.com",
            display_name="Actor",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR"}),
            must_change_password=False,
        )
        self.request_id = str(uuid4())
        self.key = str(uuid4())

    def assert_command_code(self, expected, function, **kwargs):
        with self.assertRaises(CommandError) as raised:
            function(
                actor=self.actor,
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
                **kwargs,
            )
        self.assertEqual(raised.exception.code, expected)

    def test_submit_rejects_non_uuid_attachment_before_database(self):
        self.assert_command_code(
            "INVALID_ATTACHMENT_ID",
            submit_request,
            body={
                "type_code": "EQUIPMENT",
                "payload": {},
                "attachment_ids": ["../../object"],
            },
        )

    def test_approval_requires_reason_for_negative_outcomes(self):
        self.assert_command_code(
            "DECISION_REASON_REQUIRED",
            decide_approval,
            request_id=self.request_id,
            body={"outcome": "REJECT", "reason": "short", "expected_version": 1},
        )

    def test_execution_rejects_invalid_version_and_short_result(self):
        self.assert_command_code(
            "EXPECTED_VERSION_REQUIRED",
            start_execution,
            request_id=self.request_id,
            body={"expected_version": True},
        )
        self.assert_command_code(
            "RESULT_NOTE_INVALID",
            submit_execution,
            request_id=self.request_id,
            body={
                "expected_version": 1,
                "result_note": "short",
                "external_reference": "REF-1",
            },
        )

    def test_rework_requires_actionable_reason(self):
        self.assert_command_code(
            "ACCEPTANCE_REASON_REQUIRED",
            decide_acceptance,
            request_id=self.request_id,
            body={"outcome": "REWORK", "reason": "no", "expected_version": 3},
        )

    def test_cancellation_requires_reason(self):
        self.assert_command_code(
            "CANCELLATION_REASON_REQUIRED",
            cancel_request,
            request_id=self.request_id,
            body={"expected_version": 1, "reason": "short"},
        )


class LifecycleBCompletionTests(SimpleTestCase):
    """H2: a lifecycle B request that completes must not leave an SLA stage open."""

    def test_b_completion_closes_the_open_sla_stage(self):
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        from api_core.workflow.service import (
            SQL_CLOSE_SLA_STAGE,
            _apply_execution_submission,
        )

        cursor = MagicMock()
        request_id, now = str(uuid4()), datetime.now(timezone.utc)
        status, completed_at = _apply_execution_submission(
            cursor,
            "B",
            str(uuid4()),
            str(uuid4()),
            request_id,
            "Đã hoàn tất cấp quyền",
            "ITSM-1",
            {"execution_hours": 48},
            now,
        )
        self.assertEqual((status, completed_at), ("COMPLETED", now))
        calls = [(c.args[0], c.args[1]) for c in cursor.execute.call_args_list]
        self.assertIn((SQL_CLOSE_SLA_STAGE, [now, request_id]), calls)
        # No new stage is opened after completion.
        self.assertFalse(any("INSERT INTO eas.sla_stage" in sql for sql, _ in calls))


class ConcurrencyConflictRegressionTests(SimpleTestCase):
    """Ensure concurrent cancel vs approve yields 409 Conflict instead of 404 or 5s 503."""

    def test_execute_idempotent_sets_local_lock_timeout_on_postgres(self):
        from unittest.mock import MagicMock, patch

        from api_core.workflow.service import SQL_LOCK_SECURITY, _execute_idempotent

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = lambda _s: cursor
        cursor.__exit__ = lambda _s, *a: False
        fake_conn = MagicMock()
        fake_conn.vendor = "postgresql"
        fake_conn.cursor.return_value = cursor

        with (
            patch("api_core.workflow.service.transaction.atomic"),
            patch("api_core.workflow.service.connection", fake_conn),
        ):
            res = _execute_idempotent(
                actor_id=str(uuid4()),
                scope="TEST_SCOPE",
                key=str(uuid4()),
                command_body={"x": 1},
                operation=lambda _cur: ({"ok": True}, 200, None),
            )
        self.assertEqual(res.status, 200)
        executed = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertIn("SET LOCAL lock_timeout = %s", executed)
        self.assertLess(
            executed.index("SET LOCAL lock_timeout = %s"),
            executed.index(SQL_LOCK_SECURITY),
        )

    def test_decide_approval_returns_409_when_cancelled_instance_inactive(self):
        from unittest.mock import MagicMock, patch

        actor = Actor(
            id=str(uuid4()),
            email="approver@eas.com",
            display_name="Approver",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"APPROVER"}),
            must_change_password=False,
        )
        cursor = MagicMock()
        # 1st fetchone: idempotency lookup -> None
        # 2nd fetchone: SELECT request + LEFT JOIN workflow_instance -> CANCELLED & instance None
        cursor.fetchone.side_effect = [
            None,
            (
                "CANCELLED",
                2,
                str(uuid4()),
                str(uuid4()),
                None,
                "A",
                None,
                None,
                {},
                str(uuid4()),
            ),
        ]
        cursor.__enter__ = lambda _s: cursor
        cursor.__exit__ = lambda _s, *a: False
        fake_conn = MagicMock()
        fake_conn.vendor = "postgresql"
        fake_conn.cursor.return_value = cursor

        with (
            patch("api_core.workflow.service.transaction.atomic"),
            patch("api_core.workflow.service.connection", fake_conn),
            self.assertRaises(CommandError) as ctx,
        ):
            decide_approval(
                actor=actor,
                request_id=str(uuid4()),
                body={"outcome": "APPROVE", "reason": None, "expected_version": 1},
                idempotency_key=str(uuid4()),
                correlation_id=str(uuid4()),
            )
        self.assertEqual(ctx.exception.code, "REQUEST_STATE_CONFLICT")
        self.assertEqual(ctx.exception.status, 409)
        lock_sql = next(
            c.args[0]
            for c in cursor.execute.call_args_list
            if "FROM eas.request r" in c.args[0]
        )
        self.assertIn("LEFT JOIN eas.workflow_instance", lock_sql)
        self.assertIn("FOR UPDATE OF r", lock_sql)
