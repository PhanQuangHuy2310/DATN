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
            username="actor",
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
