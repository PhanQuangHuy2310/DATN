from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from api_core.health.views import (
    EXPECTED_MOCK_RELATIONS,
    assess_mock_sources,
    assess_request_types,
    assess_runtime_role,
    storage_readiness,
)


class ReadinessLogicTests(SimpleTestCase):
    def test_mock_source_readiness_requires_every_relation_and_migration(self):
        rows = [(name, True) for name in EXPECTED_MOCK_RELATIONS]
        self.assertTrue(all(assess_mock_sources(rows, {"001", "002", "003"}).values()))
        self.assertFalse(
            assess_mock_sources(rows[:-1], {"001", "002", "003"})[
                "mock_source_contract_complete"
            ]
        )
        self.assertFalse(
            assess_mock_sources(rows, {"001"})["mock_source_migrations_current"]
        )

    def test_superuser_with_nonstandard_name_is_rejected_by_capability(self):
        checks = assess_runtime_role(
            (True, False, False, False, True, False, False, False)
        )
        self.assertFalse(checks["runtime_role_is_non_admin"])

    def test_api_role_must_not_inherit_worker_or_privacy(self):
        worker_conflict = assess_runtime_role(
            (False, False, False, False, True, True, False, False)
        )
        privacy_conflict = assess_runtime_role(
            (False, False, False, False, True, False, False, True)
        )
        self.assertFalse(worker_conflict["runtime_role_is_api_only"])
        self.assertFalse(privacy_conflict["runtime_role_is_api_only"])

    def test_valid_least_privilege_api_role_passes(self):
        checks = assess_runtime_role(
            (False, False, False, False, True, False, False, False)
        )
        self.assertTrue(all(checks.values()))

    def test_non_null_but_invalid_release_does_not_pass(self):
        rows = [("ACCESS", "B", True), ("EQUIPMENT", "C", False), ("LEAVE", "A", True)]
        checks = assess_request_types(rows, require_active_releases=True)
        self.assertTrue(checks["request_types_match_p0"])
        self.assertFalse(checks["all_active_types_configured"])

    @override_settings(
        EAS_REQUIRE_STORAGE=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="",
    )
    @patch("api_core.health.views.socket.create_connection")
    def test_storage_readiness_fails_when_private_key_is_missing(self, connect):
        connect.return_value.__enter__.return_value = None
        checks = storage_readiness()
        self.assertFalse(checks["attachment_storage_requirement_satisfied"])
        self.assertTrue(checks["malware_scanner_requirement_satisfied"])


class HealthEndpointTests(SimpleTestCase):
    def test_live_does_not_require_database(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch(
        "api_core.health.views.database_readiness",
        return_value=(True, {"database": True}),
    )
    @override_settings(EAS_REQUIRE_STORAGE=False)
    def test_ready_returns_200_when_checks_pass(self, _probe):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    @patch(
        "api_core.health.views.database_readiness",
        return_value=(False, {"runtime_role_is_non_admin": False}),
    )
    @override_settings(EAS_REQUIRE_STORAGE=False)
    def test_ready_fails_closed(self, _probe):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
