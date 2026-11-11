import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
from django.conf import settings
from django.test import SimpleTestCase

from api_core.integrations import client
from api_core.mock_sources import api
from api_core.mock_sources.service import QueryValidationError, list_resource
from api_core.workflow.errors import CommandError


class MockSourceServiceTests(SimpleTestCase):
    roles = frozenset({"OPS_ADMIN"})

    def test_limit_is_bounded(self):
        for value in ("0", "101", "x"):
            with self.subTest(value=value), self.assertRaises(QueryValidationError):
                list_resource("assets", {"limit": value}, roles=self.roles)

    def test_cursor_must_be_uuid(self):
        with self.assertRaisesRegex(QueryValidationError, "INVALID_CURSOR"):
            list_resource("employees", {"cursor": "not-a-uuid"}, roles=self.roles)

    def test_unknown_resource_is_not_interpolated_into_sql(self):
        with self.assertRaisesRegex(QueryValidationError, "RESOURCE_NOT_FOUND"):
            list_resource("assets; drop schema eas", {}, roles=self.roles)

    def test_unknown_query_parameter_is_rejected(self):
        with self.assertRaisesRegex(QueryValidationError, "UNKNOWN_QUERY_PARAMETER"):
            list_resource("assets", {"include_private": "true"}, roles=self.roles)

    @patch("api_core.mock_sources.service.connection")
    def test_cursor_page_has_stable_shape(self, db_connection):
        first_id, second_id = str(uuid4()), str(uuid4())
        context = MagicMock()
        cursor = context.__enter__.return_value
        cursor.fetchall.return_value = [
            (
                first_id,
                "LAP-001",
                "Laptop",
                "LAPTOP",
                "SN1",
                "HCM",
                "GOOD",
                "AVAILABLE",
                "2026-01-01",
            ),
            (
                second_id,
                "LAP-002",
                "Laptop 2",
                "LAPTOP",
                "SN2",
                "HCM",
                "GOOD",
                "AVAILABLE",
                "2026-01-01",
            ),
        ]
        db_connection.cursor.return_value = context
        with patch(
            "api_core.mock_sources.service.transaction.atomic", return_value=MagicMock()
        ):
            result = list_resource(
                "assets", {"limit": "1", "q": "lap"}, roles=self.roles
            )
        self.assertTrue(result["page"]["has_more"])
        self.assertEqual(result["page"]["next_cursor"], first_id)
        self.assertEqual(result["items"][0]["asset_code"], "LAP-001")
        sql, params = cursor.execute.call_args_list[-1].args
        self.assertIn("mock_assets.asset_catalog", sql)
        self.assertEqual(params[-1], 2)

    @patch("api_core.mock_sources.service.connection")
    def test_search_wildcards_are_treated_as_literals(self, db_connection):
        context = MagicMock()
        context.__enter__.return_value.fetchall.return_value = []
        db_connection.cursor.return_value = context
        with patch(
            "api_core.mock_sources.service.transaction.atomic", return_value=MagicMock()
        ):
            list_resource("assets", {"q": r"50%_off\\sale"}, roles=self.roles)
        _, params = context.__enter__.return_value.execute.call_args_list[-1].args
        self.assertEqual(params[0], r"%50\%\_off\\\\sale%")

    def test_requester_cannot_read_sensitive_company_wide_resources(self):
        for resource in (
            "leave-balances",
            "asset-loans",
            "customers",
            "contracts",
            "budgets",
        ):
            with (
                self.subTest(resource=resource),
                self.assertRaisesRegex(QueryValidationError, "RESOURCE_FORBIDDEN"),
            ):
                list_resource(resource, {}, roles=frozenset({"REQUESTER"}))


class EasDoesNotServeMockDataTests(SimpleTestCase):
    def test_old_eas_mock_routes_are_gone(self):
        # External systems are reached through their own API, never via EAS.
        self.assertEqual(self.client.get("/api/v1/mock/assets/items").status_code, 404)


class MockSystemsApiTests(SimpleTestCase):
    """The simulated external systems (EAS_SERVICE=mock)."""

    def setUp(self):
        from django.test import RequestFactory

        self.rf = RequestFactory()

    def _get(self, view, path="/x", secret=True, **kwargs):
        headers = (
            {"HTTP_X_INTEGRATION_SECRET": settings.EAS_MOCK_API_SECRET}
            if secret
            else {}
        )
        return view(self.rf.get(path, **headers), **kwargs)

    def test_secret_is_required(self):
        response = self._get(api.catalogue, secret=False, resource="assets")
        self.assertEqual(response.status_code, 401)

    def test_wrong_method_is_rejected(self):
        request = self.rf.post(
            "/x", HTTP_X_INTEGRATION_SECRET=settings.EAS_MOCK_API_SECRET
        )
        self.assertEqual(api.catalogue(request, resource="assets").status_code, 405)

    @patch("api_core.mock_sources.api.list_resource")
    def test_catalogue_serves_allowlisted_resources_only(self, service):
        service.return_value = {"items": [], "page": {"has_more": False}}
        self.assertEqual(self._get(api.catalogue, resource="assets").status_code, 200)
        self.assertEqual(
            self._get(api.catalogue, resource="pg_shadow").status_code, 404
        )

    def test_write_requires_valid_source_request_id(self):
        request = self.rf.post(
            "/x",
            data=json.dumps({"source_request_id": "not-a-uuid", "days": 1}),
            content_type="application/json",
            HTTP_X_INTEGRATION_SECRET=settings.EAS_MOCK_API_SECRET,
        )
        response = api.hr_leave_usages(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content)["error"]["code"], "INVALID_SOURCE_REQUEST_ID"
        )


class IntegrationClientTests(SimpleTestCase):
    @patch("api_core.integrations.client.disabled_apis", return_value=[])
    @patch("api_core.integrations.client.httpx.request")
    def test_business_error_keeps_code_and_status(self, request, _disabled):
        request.return_value = MagicMock(
            status_code=409, json=lambda: {"error": {"code": "RESOURCE_UNAVAILABLE"}}
        )
        with self.assertRaises(client.IntegrationError) as raised:
            client.post("assets", "assets/loans", {})
        self.assertEqual(
            (raised.exception.code, raised.exception.status),
            ("RESOURCE_UNAVAILABLE", 409),
        )
        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Integration-Secret"], settings.EAS_MOCK_API_SECRET)

    @patch("api_core.integrations.client.disabled_apis", return_value=[])
    @patch("api_core.integrations.client.httpx.request")
    def test_network_failure_is_integration_unavailable(self, request, _disabled):
        request.side_effect = httpx.ConnectError("down")
        with self.assertRaises(CommandError) as raised:
            client.get("hr", "hr/employees")
        self.assertEqual(raised.exception.code, "INTEGRATION_UNAVAILABLE")

    @patch(
        "api_core.integrations.client.disabled_apis",
        return_value=[("API_HR", "hr", "HRM")],
    )
    @patch("api_core.integrations.client.httpx.request")
    def test_admin_switch_blocks_calls(self, request, _disabled):
        with self.assertRaises(CommandError) as raised:
            client.get("hr", "hr/employees")
        self.assertEqual(raised.exception.code, "INTEGRATION_DISABLED")
        request.assert_not_called()
