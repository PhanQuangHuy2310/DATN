from datetime import datetime, timezone
from typing import ClassVar

from django.test import SimpleTestCase

from api_core.administration import analytics, workflows
from api_core.workflow.service import CommandError


class WorkflowMappingTests(SimpleTestCase):
    def test_automation_weight_round_trips_risk(self):
        for risk in range(1, 6):
            self.assertEqual(
                workflows._risk_from_automation(workflows._automation_weight(risk)),
                risk,
            )

    def test_invalid_automation_weight_rejected(self):
        for bad in (-1, 101, "50", True, None):
            with self.assertRaises(CommandError):
                workflows._risk_from_automation(bad)

    def test_lifecycle_steps(self):
        stages = {
            lc: [s["stage"] for s in workflows._lifecycle_steps(lc)] for lc in "ABC"
        }
        self.assertEqual(stages["A"], ["YEU_CAU", "PHE_DUYET", "HOAN_THANH"])
        self.assertIn("THUC_HIEN", stages["B"])
        self.assertNotIn("NGHIEM_THU", stages["B"])
        self.assertEqual(stages["C"][-2], "NGHIEM_THU")
        steps = workflows._lifecycle_steps(
            "A", ["DIRECT_MANAGER", "DIRECTOR"], {"approval_hours": 24}
        )
        self.assertEqual(steps[1]["actor"], "Quản lý trực tiếp, Ban giám đốc")
        self.assertEqual(steps[1]["sla_hours"], 24)

    def test_sla_hours_sums_profile(self):
        self.assertEqual(
            workflows._sla_hours({"approval_hours": 24, "execution_hours": 8}), 32
        )
        self.assertIsNone(workflows._sla_hours(None))


class AnalyticsBucketTests(SimpleTestCase):
    def test_buckets_use_vietnam_time_and_known_labels(self):
        # 2026-11-02 18:30 UTC = Tuesday 2026-11-03 01:30 in Vietnam.
        created = datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc)
        expected = {"day": "00:00", "week": "Thứ 3", "month": "Tuần 1", "year": "T11"}
        for period, label in expected.items():
            self.assertEqual(analytics._bucket(period, created), label)
            self.assertIn(label, analytics._bucket_labels(period))

    def test_outcome(self):
        self.assertEqual(analytics._outcome("COMPLETED"), "success")
        self.assertEqual(analytics._outcome("CANCELLED"), "rejected")
        self.assertEqual(analytics._outcome("PENDING_APPROVAL"), "processing")


class AnalyticsEndpointTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def test_analytics_view_returns_status_breakdown(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        actor = SimpleNamespace(
            id="u-1",
            email="admin@eas.com",
            display_name="Admin",
            roles=frozenset({"OPS_ADMIN"}),
            must_change_password=False,
        )
        now = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
        rows = [
            (now, "COMPLETED", "A", "Nghỉ phép", "Nhân sự", "A", "a@eas.com", 5.0, 12),
            (now, "COMPLETED", "A", "WFH", "Nhân sự", "A", "a@eas.com", 4.0, 12),
            (
                now,
                "PENDING_APPROVAL",
                "B",
                "IT",
                "Kỹ thuật",
                "B",
                "b@eas.com",
                None,
                24,
            ),
            (
                now,
                "READY_FOR_EXECUTION",
                "C",
                "Mua sắm",
                "Kinh doanh",
                "C",
                "c@eas.com",
                None,
                72,
            ),
            (now, "REJECTED", "C", "Mua sắm", "Kinh doanh", "C", "c@eas.com", 15.0, 72),
        ]
        cur = MagicMock()
        cur.fetchall.return_value = rows
        with (
            patch("api_core.authn.service.load_actor_from_session", return_value=actor),
            patch("api_core.administration.analytics.connection.cursor") as mock_cur,
        ):
            mock_cur.return_value.__enter__.return_value = cur
            res = self.client.get("/api/v1/admin/analytics?period=month")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(
            body["status_breakdown"],
            {
                "COMPLETED": 2,
                "PENDING_APPROVAL": 1,
                "READY_FOR_EXECUTION": 1,
                "REJECTED": 1,
            },
        )
        self.assertEqual(body["kpis"]["total_requests"], 5)
        self.assertEqual(body["kpis"]["success_count"], 2)
        self.assertEqual(body["kpis"]["processing_count"], 2)
        self.assertEqual(body["kpis"]["rejected_count"], 1)


class IntegrationMappingTests(SimpleTestCase):
    def test_disabled_api_closes_its_catalogue_groups(self):
        from api_core.catalog import integrations

        self.assertTrue(integrations.blocks("hr", "LEAVE", "TIME"))
        self.assertTrue(integrations.blocks("travel", "BUSINESS_TRIP", "HR"))
        self.assertTrue(
            integrations.blocks("procurement", "PURCHASE_REQUEST", "FINANCE")
        )
        self.assertTrue(integrations.blocks("crm", "SPECIAL_DISCOUNT", "SALES"))
        self.assertFalse(integrations.blocks("it", "LEAVE", "TIME"))
        self.assertFalse(integrations.blocks("travel", "IT_SUPPORT", "IT"))


class AdminModuleGrantTests(SimpleTestCase):
    def test_system_modules_never_granted_to_employees(self):
        from unittest.mock import MagicMock

        from api_core.administration.org_users_rbac import _assert_grantable

        cur = MagicMock()
        cur.fetchone.return_value = (1,)
        for module in ("permissions", "ai_engine", "api_management", "system_versions"):
            with self.assertRaises(CommandError):
                _assert_grantable(cur, module, True, employee=True)
            _assert_grantable(cur, module, False, employee=True)  # revoking is fine
            _assert_grantable(cur, module, True, employee=False)  # admin roles
        # Business modules the admin may delegate (spec: users, regulations...).
        for module in ("users", "regulations", "org_chart", "dashboard"):
            _assert_grantable(cur, module, True, employee=True)
        cur.fetchone.return_value = None
        with self.assertRaises(CommandError):
            _assert_grantable(cur, "nope", True, employee=True)
