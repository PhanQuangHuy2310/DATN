from datetime import datetime, timezone

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
