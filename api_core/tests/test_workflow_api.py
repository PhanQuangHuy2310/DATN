import json
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow.service import CommandError, CommandResult


class WorkflowApiContractTests(SimpleTestCase):
    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()),
            username="requester",
            display_name="Requester",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )

    @patch("api_core.authn.service.load_actor_from_session")
    def test_submit_requires_idempotency_key_before_service(self, load_actor):
        load_actor.return_value = self.actor
        response = self.client.post(
            "/api/v1/requests/submit",
            data=json.dumps({"type_code": "LEAVE", "payload": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")

    @patch("api_core.workflow.views.submit_request")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_submit_exposes_replay_and_correlation_headers(self, load_actor, submit):
        load_actor.return_value = self.actor
        submit.return_value = CommandResult(
            {"request": {"id": str(uuid4()), "status": "PENDING_APPROVAL"}},
            201,
            replayed=True,
        )
        response = self.client.post(
            "/api/v1/requests/submit",
            data=json.dumps({"type_code": "LEAVE", "payload": {}}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["X-Idempotent-Replay"], "true")
        self.assertIn("X-Correlation-ID", response.headers)

    @patch("api_core.workflow.views.submit_request")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_domain_conflict_uses_stable_error_envelope(self, load_actor, submit):
        load_actor.return_value = self.actor
        submit.side_effect = CommandError("VERSION_CONFLICT", status=409)
        response = self.client.post(
            "/api/v1/requests/submit",
            data=json.dumps({"type_code": "LEAVE", "payload": {}}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "VERSION_CONFLICT")
        self.assertIn("correlation_id", response.json())

    def test_unauthenticated_request_list_fails_closed(self):
        response = self.client.get("/api/v1/requests")
        self.assertEqual(response.status_code, 401)
