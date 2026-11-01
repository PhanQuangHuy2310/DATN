"""Items 4.4-4.5: approval delegation, absent-approver escalation and the
HRM attendance match (employee code first, email as fallback)."""

from datetime import datetime, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from api_core.authn.models import Actor
from api_core.management.commands.sync_employee_codes import (
    match_employees,
    normalize_name,
)
from api_core.workflow.delegation import create_delegation, validate_delegation
from api_core.workflow.service import (
    SQL_ATTENDANCE_MATCH,
    CommandError,
    _apply_acceptance_decision,
    _substitute_approver,
)


def _actor(roles=("APPROVER",)):
    return Actor(
        id=str(uuid4()),
        email="approver@eas.com",
        display_name="Approver",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


def _sql(cursor):
    return " ".join(c.args[0] for c in cursor.execute.call_args_list)


class SubstituteApproverTests(SimpleTestCase):
    def setUp(self):
        self.step = str(uuid4())
        self.assignee = str(uuid4())
        self.instance = str(uuid4())

    def substitute(self, fetches):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetches
        with patch("api_core.workflow.service._append_request_audit") as audit:
            change = _substitute_approver(
                cursor,
                step_id=self.step,
                request_id=str(uuid4()),
                requester_id=str(uuid4()),
                department_id=str(uuid4()),
                type_id=str(uuid4()),
                correlation_id="c",
            )
        return change, cursor, audit

    def test_active_delegate_takes_the_step(self):
        delegate = str(uuid4())
        change, cursor, audit = self.substitute(
            [
                (self.instance, self.assignee),
                (True,),  # delegation table installed
                (delegate,),  # active delegation
                None,  # delegate holds no other step in the route
                (True,),  # delegate is an approver in scope
            ]
        )
        self.assertEqual(change["assignee_id"], delegate)
        self.assertEqual(change["reason"], "DELEGATED")
        update = next(
            c
            for c in cursor.execute.call_args_list
            if "UPDATE eas.approval_step" in c.args[0]
        )
        self.assertEqual(update.args[1], [delegate, self.step])
        self.assertIn("INSERT INTO eas.request_participant", _sql(cursor))
        self.assertEqual(audit.call_args.kwargs["action"], "APPROVER_SUBSTITUTED")

    def test_absent_approver_without_delegate_escalates_to_manager(self):
        manager = str(uuid4())
        change, _, _ = self.substitute(
            [
                (self.instance, self.assignee),
                (True,),
                None,  # no active delegation
                (True,),  # attendance feed installed
                ("ABSENT",),
                (manager,),
                None,
                (True,),
            ]
        )
        self.assertEqual(change["assignee_id"], manager)
        self.assertEqual(change["reason"], "APPROVER_ABSENT_ESCALATED")

    def test_delegate_already_in_route_falls_back_to_attendance_rule(self):
        change, cursor, _ = self.substitute(
            [
                (self.instance, self.assignee),
                (True,),
                (str(uuid4()),),
                (1,),  # delegate already holds a step: SoD
                (True,),
                ("PRESENT",),
            ]
        )
        self.assertIsNone(change)
        self.assertNotIn("UPDATE eas.approval_step", _sql(cursor))

    def test_present_approver_without_delegate_keeps_step(self):
        change, _, audit = self.substitute(
            [(self.instance, self.assignee), (True,), None, (True,), None]
        )
        self.assertIsNone(change)
        audit.assert_not_called()

    def test_features_not_installed_change_nothing(self):
        change, _, _ = self.substitute(
            [(self.instance, self.assignee), (False,), (False,)]
        )
        self.assertIsNone(change)


class ReworkSubstitutionTests(SimpleTestCase):
    @patch("api_core.workflow.service._is_actor_valid_for_role", return_value=True)
    def test_rework_goes_to_present_colleague_when_executor_absent(self, _valid):
        substitute = str(uuid4())
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (str(uuid4()), None),  # requester, acceptor
            (True,),  # attendance feed
            ("LEAVE",),
            (substitute,),
        ]
        status, _, _ = _apply_acceptance_decision(
            cursor,
            "REWORK",
            str(uuid4()),
            str(uuid4()),
            1,
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            {"execution_hours": 8},
            datetime.now(timezone.utc),
        )
        self.assertEqual(status, "READY_FOR_EXECUTION")
        attempt = next(
            c
            for c in cursor.execute.call_args_list
            if "INSERT INTO eas.execution_attempt" in c.args[0]
        )
        self.assertEqual(attempt.args[1][-1], substitute)


class DelegationValidationTests(SimpleTestCase):
    def body(self, **changes):
        start = datetime(2026, 11, 3, tzinfo=timezone.utc)
        return {
            "delegate_id": str(uuid4()),
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(days=7)).isoformat(),
            "reason": "Nghỉ phép năm",
            **changes,
        }

    def test_valid_window(self):
        data = validate_delegation(_actor(), self.body())
        self.assertEqual(data["ends_at"] - data["starts_at"], timedelta(days=7))

    def test_invalid_delegations_are_rejected(self):
        actor = _actor()
        start = datetime(2026, 11, 3, tzinfo=timezone.utc)
        for body in (
            self.body(delegate_id=actor.id),
            self.body(ends_at=(start + timedelta(days=91)).isoformat()),
            self.body(ends_at=start.isoformat()),
            self.body(starts_at="2026-11-03T00:00:00"),
            self.body(reason="ok"),
            {"delegate_id": str(uuid4())},
        ):
            with self.subTest(body=body), self.assertRaises(CommandError):
                validate_delegation(actor, body)


class DelegationStoreTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def create(self, fetches):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetches
        body = DelegationValidationTests().body()
        with (
            patch("api_core.workflow.delegation.transaction.atomic"),
            patch("api_core.workflow.delegation.connection.cursor") as cm,
            patch("api_core.workflow.delegation._append_admin_audit") as audit,
        ):
            cm.return_value.__enter__.return_value = cursor
            result = create_delegation(actor=_actor(), body=body, correlation_id="c")
        return result, cursor, audit

    def test_create_records_and_audits(self):
        result, cursor, audit = self.create([(True,), (1,), None, (str(uuid4()),)])
        self.assertIn("INSERT INTO eas.approval_delegation", _sql(cursor))
        self.assertEqual(
            audit.call_args.kwargs["action"], "APPROVAL_DELEGATION_CREATED"
        )
        self.assertIn("id", result)

    def test_delegate_must_be_an_approver(self):
        with self.assertRaises(CommandError) as raised:
            self.create([(True,), None])
        self.assertEqual(raised.exception.code, "DELEGATE_NOT_APPROVER")

    def test_overlapping_window_is_rejected(self):
        with self.assertRaises(CommandError) as raised:
            self.create([(True,), (1,), (1,)])
        self.assertEqual(raised.exception.code, "DELEGATION_OVERLAP")

    def test_not_installed_returns_503(self):
        with self.assertRaises(CommandError) as raised:
            self.create([(False,)])
        self.assertEqual(raised.exception.status, 503)


class DelegationApiAccessTests(SimpleTestCase):
    def test_only_approvers_reach_delegations(self):
        from api_core.workflow.views import delegations_view

        request = RequestFactory().get("/api/v1/delegations")
        with patch(
            "api_core.authn.service.load_actor_from_session",
            return_value=_actor(("REQUESTER",)),
        ):
            self.assertEqual(delegations_view(request).status_code, 403)


class EmployeeCodeMatchingTests(SimpleTestCase):
    def test_email_first_then_unique_name(self):
        accounts = [
            ("a1", "an.nguyen@eas.com", "Nguyễn Minh An"),
            ("a2", "ngoc.tran@eas.com", "Trần Thị Bích Ngọc"),
            ("a3", "x@eas.com", "Không Có Trong HRM"),
        ]
        employees = [
            ("E1", "an.nguyen@eas.com", "Nguyen Minh An"),
            ("E2", "ngoc.tran@example.test", "TRẦN THỊ BÍCH NGỌC"),
            ("E3", "other@example.test", "Người Khác"),
        ]
        matches, unmatched, unused, ambiguous = match_employees(accounts, employees)
        self.assertEqual(matches, {"a1": ("E1", "email"), "a2": ("E2", "name")})
        self.assertEqual([a[0] for a in unmatched], ["a3"])
        self.assertEqual(unused, ["E3"])
        self.assertEqual(ambiguous, [])

    def test_duplicate_names_are_reported_not_guessed(self):
        accounts = [("a1", "x@eas.com", "Lê Văn Hải")]
        employees = [
            ("E1", "h1@example.test", "Lê Văn Hải"),
            ("E2", "h2@example.test", "Le Van Hai"),
        ]
        matches, unmatched, _, ambiguous = match_employees(accounts, employees)
        self.assertEqual(matches, {})
        self.assertEqual(ambiguous, ["Lê Văn Hải"])
        self.assertEqual(len(unmatched), 1)

    def test_vietnamese_names_normalize(self):
        self.assertEqual(normalize_name("  Đặng   Quốc Tuấn "), "dang quoc tuan")


class AttendanceMatchSqlTests(SimpleTestCase):
    def test_code_wins_and_email_is_fallback(self):
        sql = " ".join(SQL_ATTENDANCE_MATCH.split())
        self.assertIn(
            "THEN to_jsonb(a)->>'employee_code' = to_jsonb(u)->>'employee_code'", sql
        )
        self.assertIn("ELSE a.employee_email = u.email", sql)
