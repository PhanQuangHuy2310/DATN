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

    @patch("api_core.integrations.ai_service.ai_client_sync.classify_request")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_ai_classify_proxy_endpoint(self, load_actor, mock_classify):
        load_actor.return_value = self.actor
        mock_classify.return_value = {
            "predicted_request_type": "leave_annual",
            "predicted_department": "hr",
            "predicted_template": "A",
            "confidence_request_type": 0.95,
        }
        response = self.client.post(
            "/api/v1/ai/classify",
            data=json.dumps(
                {
                    "title": "Xin nghỉ phép hè 3 ngày",
                    "description": "Đi du lịch cùng gia đình",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["predicted_request_type"], "leave_annual"
        )
        self.assertIn("correlation_id", response.json())

    @patch("api_core.integrations.ai_service.ai_client_sync.score_risk")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_ai_risk_score_proxy_endpoint(self, load_actor, mock_score):
        load_actor.return_value = self.actor
        mock_score.return_value = {
            "risk_score": 2,
            "risk_label": "medium",
            "confidence": 0.88,
            "auto_approve_eligible": True,
        }
        response = self.client.post(
            "/api/v1/ai/risk-score",
            data=json.dumps(
                {
                    "request_type": "leave_annual",
                    "lifecycle_template": "A",
                    "risk_weight": 2,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["risk_score"], 2)

    @patch("api_core.integrations.ai_service.ai_client_sync.summarize_request")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_ai_summarize_proxy_endpoint(self, load_actor, mock_summarize):
        load_actor.return_value = self.actor
        mock_summarize.return_value = {
            "summary": "Nhân viên xin nghỉ phép 3 ngày",
            "key_points": ["3 ngày phép", "Có bàn giao"],
        }
        response = self.client.post(
            "/api/v1/ai/summarize",
            data=json.dumps(
                {"title": "Xin nghỉ phép hè", "request_type": "leave_annual"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["summary"], "Nhân viên xin nghỉ phép 3 ngày"
        )

    def test_ai_endpoints_require_authentication(self):
        for path in (
            "/api/v1/ai/classify",
            "/api/v1/ai/risk-score",
            "/api/v1/ai/summarize",
        ):
            with self.subTest(path=path):
                response = self.client.post(
                    path, data="{}", content_type="application/json"
                )
                self.assertEqual(response.status_code, 401)
