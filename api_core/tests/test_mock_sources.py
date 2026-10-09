from dataclasses import replace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.db import OperationalError
from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.mock_sources.service import QueryValidationError, list_resource


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


class MockSourceApiTests(SimpleTestCase):
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

    def test_unauthenticated_access_fails_closed(self):
        response = self.client.get("/api/v1/mock/assets/items")
        self.assertEqual(response.status_code, 401)

    @patch("api_core.mock_sources.views.list_resource")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_authenticated_response_has_envelope_and_correlation(self, auth, service):
        auth.return_value = self.actor
        service.return_value = {"items": [], "page": {"has_more": False}}
        response = self.client.get("/api/v1/mock/assets/items")
        self.assertEqual(response.status_code, 200)
        self.assertIn("correlation_id", response.json())
        self.assertIn("X-Correlation-ID", response.headers)

    @patch("api_core.authn.service.load_actor_from_session")
    def test_bad_limit_has_stable_error(self, auth):
        auth.return_value = self.actor
        response = self.client.get("/api/v1/mock/assets/items?limit=1000")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_LIMIT")
        self.assertEqual(
            response.json()["correlation_id"], response.headers["X-Correlation-ID"]
        )

    @patch("api_core.authn.service.load_actor_from_session")
    def test_requester_is_forbidden_from_company_wide_leave_balances(self, auth):
        auth.return_value = self.actor
        response = self.client.get("/api/v1/mock/hr/leave-balances")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "RESOURCE_FORBIDDEN")

    @patch("api_core.mock_sources.views.list_resource")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_sensitive_resource_is_never_cached(self, auth, service):
        auth.return_value = replace(self.actor, roles=frozenset({"OPS_ADMIN"}))
        service.return_value = {"items": [], "page": {"has_more": False}}
        response = self.client.get("/api/v1/mock/finance/budgets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    @patch("api_core.mock_sources.views.list_resource")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_database_failure_is_redacted_as_stable_503(self, auth, service):
        auth.return_value = self.actor
        service.side_effect = OperationalError("credential text must not escape")
        response = self.client.get("/api/v1/mock/assets/items")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "SOURCE_UNAVAILABLE")
        self.assertNotContains(response, "credential text", status_code=503)
        self.assertEqual(
            response.json()["correlation_id"], response.headers["X-Correlation-ID"]
        )

    @patch("api_core.mock_sources.views.list_resource")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_all_contract_routes_map_to_allowlisted_resources(self, auth, service):
        auth.return_value = replace(self.actor, roles=frozenset({"OPS_ADMIN"}))
        service.return_value = {"items": [], "page": {"has_more": False}}
        routes = {
            "hr/departments": "departments",
            "hr/employees": "employees",
            "hr/leave-balances": "leave-balances",
            "assets/items": "assets",
            "assets/loans": "asset-loans",
            "facilities/resources": "facilities",
            "crm/customers": "customers",
            "crm/contracts": "contracts",
            "procurement/suppliers": "suppliers",
            "procurement/catalog-items": "catalog-items",
            "it/applications": "applications",
            "it/access-roles": "access-roles",
            "it/services": "it-services",
            "finance/budgets": "budgets",
            "finance/expense-categories": "expense-categories",
            "travel/policies": "travel-policies",
            "travel/options": "travel-options",
        }
        for route, resource in routes.items():
            with self.subTest(route=route):
                response = self.client.get(f"/api/v1/mock/{route}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(service.call_args.args[0], resource)
