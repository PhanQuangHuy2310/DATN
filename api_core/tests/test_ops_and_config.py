from __future__ import annotations

import json
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.domain.validation import PayloadValidationError, validate_draft_payload
from api_core.workflow.config_service import (
    create_or_clone_release,
    publish_config_release,
)
from api_core.workflow.ops_service import (
    reassign_actor,
)
from api_core.workflow.service import (
    CommandError,
    CommandResult,
    report_execution_issue,
    update_draft,
)


class OpsAndConfigBoundaryTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.ops_actor = Actor(
            id=str(uuid4()),
            username="ops_admin",
            display_name="Operations Admin",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"OPS_ADMIN"}),
            must_change_password=False,
        )
        self.policy_actor = Actor(
            id=str(uuid4()),
            username="policy_admin",
            display_name="Policy Admin",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"POLICY_ADMIN"}),
            must_change_password=False,
        )
        self.requester_actor = Actor(
            id=str(uuid4()),
            username="requester",
            display_name="Requester",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )
        self.executor_actor = Actor(
            id=str(uuid4()),
            username="executor",
            display_name="Executor",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"EXECUTOR"}),
            must_change_password=False,
        )
        self.key = str(uuid4())
        self.request_id = str(uuid4())

    def test_update_draft_rejects_mass_assignment(self):
        # TC013, TC073: Unknown / immutable fields in body or payload
        with self.assertRaises(CommandError) as raised:
            update_draft(
                actor=self.requester_actor,
                request_id=self.request_id,
                body={"expected_version": 1, "status": "APPROVED"},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")

        with self.assertRaises(CommandError) as raised:
            update_draft(
                actor=self.requester_actor,
                request_id=self.request_id,
                body={"expected_version": 1, "payload": {"owner_id": str(uuid4())}},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "UNKNOWN_FIELD")

    def test_validate_draft_payload_allows_missing_required_fields(self):
        # Draft validation should be lenient with missing required fields
        form_schema = {
            "schema_version": 1,
            "type": "object",
            "properties": {
                "reason": {"type": "string", "minLength": 5, "maxLength": 100},
                "start_date": {"type": "string", "format": "date"},
            },
            "required": ["reason", "start_date"],
            "additionalProperties": False,
        }
        partial = {"reason": "Personal matters"}
        cleaned = validate_draft_payload(
            type_code="LEAVE",
            payload=partial,
            form_schema=form_schema,
            requester_id=self.requester_actor.id,
        )
        self.assertEqual(cleaned["reason"], "Personal matters")
        self.assertNotIn("start_date", cleaned)

    def test_validate_draft_payload_rejects_html_injection(self):
        form_schema = {
            "schema_version": 1,
            "type": "object",
            "properties": {
                "reason": {"type": "string", "minLength": 2, "maxLength": 100},
            },
            "additionalProperties": False,
        }
        with self.assertRaises(PayloadValidationError):
            validate_draft_payload(
                type_code="LEAVE",
                payload={"reason": "<script>alert(1)</script>"},
                form_schema=form_schema,
                requester_id=self.requester_actor.id,
            )

    def test_report_execution_issue_validates_kind_and_reason(self):
        # Invalid kind
        with self.assertRaises(CommandError) as raised:
            report_execution_issue(
                actor=self.executor_actor,
                request_id=self.request_id,
                body={
                    "expected_version": 1,
                    "kind": "INVALID_KIND",
                    "reason": "A valid reason here",
                },
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "INVALID_ISSUE_KIND")

        # Short reason (< 10 chars)
        with self.assertRaises(CommandError) as raised:
            report_execution_issue(
                actor=self.executor_actor,
                request_id=self.request_id,
                body={"expected_version": 1, "kind": "BLOCKED", "reason": "too short"},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "ISSUE_REASON_INVALID")

    def test_reassign_actor_validates_target_kind_and_reason(self):
        # Invalid target kind
        with self.assertRaises(CommandError) as raised:
            reassign_actor(
                actor=self.ops_actor,
                request_id=self.request_id,
                body={
                    "expected_version": 1,
                    "target_kind": "INVALID_TARGET",
                    "target_id": str(uuid4()),
                    "new_user_id": str(uuid4()),
                    "reason": "Reassigning due to absence of original assignee",
                },
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "UNKNOWN_TARGET_KIND")

        # Reason too short
        with self.assertRaises(CommandError) as raised:
            reassign_actor(
                actor=self.ops_actor,
                request_id=self.request_id,
                body={
                    "expected_version": 1,
                    "target_kind": "APPROVAL_STEP",
                    "target_id": str(uuid4()),
                    "new_user_id": str(uuid4()),
                    "reason": "short",
                },
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "REASON_INVALID")

    @patch("api_core.workflow.config_service._execute_idempotent")
    def test_config_release_clone_validates_type_code(self, mock_exec):
        with self.assertRaises(CommandError) as raised_syntax:
            create_or_clone_release(
                actor=self.policy_actor,
                body={"type_code": "invalid-type"},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised_syntax.exception.code, "UNKNOWN_TYPE_CODE")

        def _invoke_op(*args, **kwargs):
            op = kwargs.get("operation")
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            return op(mock_cursor)

        mock_exec.side_effect = _invoke_op
        with self.assertRaises(CommandError) as raised:
            create_or_clone_release(
                actor=self.policy_actor,
                body={"type_code": "NON_EXISTENT_TYPE"},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "UNKNOWN_TYPE_CODE")

    @patch("api_core.workflow.config_service._execute_idempotent")
    def test_config_release_publish_immutable_published(self, mock_exec):
        # TC011: Attempting to update or publish an already published release fails
        def _invoke_op(*args, **kwargs):
            op = kwargs.get("operation")
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (
                str(uuid4()),  # cr.id
                str(uuid4()),  # rt.id
                "LEAVE",  # rt.code
                1,  # cr.version
                "PUBLISHED",  # cr.state
                "A",  # cr.lifecycle
                {},  # cr.form_schema
                [],  # cr.route_rules
                {},  # cr.actor_bindings
                {},  # cr.sla_profile
                1,  # cr.lock_version
            )
            return op(mock_cursor)

        mock_exec.side_effect = _invoke_op
        release_id = str(uuid4())

        with self.assertRaises(CommandError) as raised:
            publish_config_release(
                actor=self.policy_actor,
                release_id=release_id,
                body={"expected_version": 1},
                idempotency_key=self.key,
                correlation_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "RELEASE_IMMUTABLE")


class OpsAndConfigHttpContractTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.ops_actor = Actor(
            id=str(uuid4()),
            username="ops_admin",
            display_name="Operations Admin",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"OPS_ADMIN"}),
            must_change_password=False,
        )
        self.policy_actor = Actor(
            id=str(uuid4()),
            username="policy_admin",
            display_name="Policy Admin",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"POLICY_ADMIN"}),
            must_change_password=False,
        )
        self.requester_actor = Actor(
            id=str(uuid4()),
            username="requester",
            display_name="Requester",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )

    @patch("api_core.workflow.views.list_ops_metadata")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_ops_requests_view_whitelist_only(self, load_actor, list_ops):
        load_actor.return_value = self.ops_actor
        list_ops.return_value = {
            "items": [
                {
                    "id": str(uuid4()),
                    "code": "REQ-2026-0001",
                    "type_code": "LEAVE",
                    "status": "PENDING_APPROVAL",
                    "lock_version": 1,
                    "department_id": str(uuid4()),
                }
            ],
            "next_offset": None,
        }
        response = self.client.get("/api/v1/ops/requests")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        item = data["items"][0]
        # TC024 Whitelist verification: payload/title/notes must NOT exist
        self.assertNotIn("payload", item)
        self.assertNotIn("title", item)
        self.assertNotIn("result_note", item)

    @patch("api_core.authn.service.load_actor_from_session")
    def test_ops_requests_forbidden_for_requester(self, load_actor):
        load_actor.return_value = self.requester_actor
        response = self.client.get("/api/v1/ops/requests")
        self.assertEqual(response.status_code, 403)

    @patch("api_core.workflow.views.reassign_actor")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_reassign_actor_http_flow(self, load_actor, reassign_mock):
        load_actor.return_value = self.ops_actor
        req_id = str(uuid4())
        reassign_mock.return_value = CommandResult(
            {
                "request": {
                    "id": req_id,
                    "status": "PENDING_APPROVAL",
                    "lock_version": 2,
                }
            },
            200,
        )
        response = self.client.post(
            f"/api/v1/requests/{req_id}/reassign",
            data=json.dumps(
                {
                    "expected_version": 1,
                    "target_kind": "APPROVAL_STEP",
                    "target_id": str(uuid4()),
                    "new_user_id": str(uuid4()),
                    "reason": "Assignee on unexpected annual leave.",
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Correlation-ID", response.headers)

    @patch("api_core.workflow.views.validate_release_candidate")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_config_release_validate_endpoint(self, load_actor, validate_mock):
        load_actor.return_value = self.policy_actor
        release_id = str(uuid4())
        validate_mock.return_value = {
            "valid": True,
            "validation_hash": "a" * 64,
            "lock_version": 1,
        }
        response = self.client.post(f"/api/v1/config-releases/{release_id}/validate")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["validation_hash"], "a" * 64)

    @patch("api_core.workflow.views.update_draft")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_patch_request_draft_endpoint(self, load_actor, update_draft_mock):
        load_actor.return_value = self.requester_actor
        req_id = str(uuid4())
        update_draft_mock.return_value = CommandResult(
            {"request": {"id": req_id, "status": "DRAFT", "lock_version": 1}},
            200,
        )
        response = self.client.patch(
            f"/api/v1/requests/{req_id}",
            data=json.dumps(
                {"expected_version": 0, "payload": {"reason": "Updated description"}}
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request"]["status"], "DRAFT")

    @patch("api_core.workflow.views.get_attachment_metadata")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_attachment_metadata_anti_idor(self, load_actor, get_meta_mock):
        load_actor.return_value = self.requester_actor
        att_id = str(uuid4())
        get_meta_mock.side_effect = CommandError("NOT_FOUND", status=404)
        response = self.client.get(f"/api/v1/attachments/{att_id}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")
