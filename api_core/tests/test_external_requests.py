"""Request rules that use the external systems, and the request taxonomy."""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.integrations import requests as ext
from api_core.workflow.errors import CommandError

ROOT = Path(__file__).resolve().parents[2]
APPS = [
    {"code": "AWS", "name": "AWS", "status": "ACTIVE"},
    {"code": "JIRA", "name": "Jira", "status": "ACTIVE"},
]
ROLES = [
    {
        "code": "AWS_READONLY",
        "name": "RO",
        "app_code": "AWS",
        "risk_level": "MEDIUM",
        "status": "ACTIVE",
    },
]


def _cursor(department="TECH"):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("staff@eas.com", department)
    return cursor


class PickerValidationTests(SimpleTestCase):
    def _fake_get(self, system, path, **params):
        return {
            "it/applications": {"items": APPS},
            "it/access-roles": {"items": ROLES},
            "finance/expense-categories": {
                "items": [
                    {
                        "code": "MEAL",
                        "name": "Ăn uống",
                        "daily_limit_minor": 500000,
                        "status": "ACTIVE",
                    }
                ]
            },
        }[path]

    def test_codes_must_exist_in_the_external_catalogue(self):
        with (
            patch.object(ext.client, "get", side_effect=self._fake_get),
            self.assertRaises(CommandError) as raised,
        ):
            ext.validate_submit(
                _cursor(),
                type_code="ACCESS",
                payload={
                    "app_code": "PRODUCTION_DB",
                    "requested_role": "AWS_READONLY",
                },
                amount=None,
                requester_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.fields["app_code"], ["UNKNOWN_EXTERNAL_CODE"])

    def test_role_must_belong_to_the_application(self):
        with (
            patch.object(ext.client, "get", side_effect=self._fake_get),
            self.assertRaises(CommandError) as raised,
        ):
            ext.validate_submit(
                _cursor(),
                type_code="ACCESS",
                payload={"app_code": "JIRA", "requested_role": "AWS_READONLY"},
                amount=None,
                requester_id=str(uuid4()),
            )
        self.assertIn(
            "ROLE_NOT_IN_APPLICATION", raised.exception.fields["requested_role"]
        )

    def test_expense_daily_limit_comes_from_erp(self):
        with (
            patch.object(ext.client, "get", side_effect=self._fake_get),
            self.assertRaises(CommandError) as raised,
        ):
            ext.validate_submit(
                _cursor(),
                type_code="EXPENSE_CLAIM",
                payload={"expense_category": "MEAL"},
                amount=900000,
                requester_id=str(uuid4()),
            )
        self.assertEqual(
            raised.exception.fields["amount_vnd"], ["EXPENSE_DAILY_LIMIT_EXCEEDED"]
        )


class LeaveAndBudgetTests(SimpleTestCase):
    def test_paid_leave_beyond_hrm_balance_is_refused(self):
        balances = {"items": [{"leave_type": "ANNUAL", "remaining_days": 2}]}
        with (
            patch.object(ext.client, "get", return_value=balances) as get,
            self.assertRaises(CommandError) as raised,
        ):
            ext.validate_submit(
                _cursor(),
                type_code="LEAVE",
                payload={
                    "leave_kind": "CO_LUONG",
                    "start_date": "2026-11-10",
                    "end_date": "2026-11-12",
                },
                amount=None,
                requester_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "LEAVE_BALANCE_EXCEEDED")
        self.assertEqual(get.call_args.kwargs["employee_email"], "staff@eas.com")

    def test_unpaid_leave_needs_no_balance(self):
        with patch.object(ext.client, "get") as get:
            ext.validate_submit(
                _cursor(),
                type_code="LEAVE",
                payload={
                    "leave_kind": "KHONG_LUONG",
                    "start_date": "2026-11-10",
                    "end_date": "2026-11-20",
                },
                amount=None,
                requester_id=str(uuid4()),
            )
        get.assert_not_called()

    def test_budget_checked_against_requester_department(self):
        with (
            patch.object(
                ext.client, "get", return_value={"available_minor": 1000}
            ) as get,
            self.assertRaises(CommandError) as raised,
        ):
            ext.validate_submit(
                _cursor("FIN"),
                type_code="PURCHASE_REQUEST",
                payload={},
                amount=5000,
                requester_id=str(uuid4()),
            )
        self.assertEqual(raised.exception.code, "BUDGET_EXCEEDED")
        self.assertEqual(get.call_args.kwargs["department_code"], "FIN")

    def test_final_approval_records_usage_and_commitment(self):
        request_id = str(uuid4())
        with patch.object(ext.client, "post", return_value={"status": "OK"}) as post:
            ext.on_final_approval(
                _cursor(),
                request_id=request_id,
                type_code="LEAVE",
                payload={
                    "leave_kind": "CO_LUONG",
                    "start_date": "2026-11-10",
                    "end_date": "2026-11-11",
                },
                amount=None,
                requester_id=str(uuid4()),
            )
        path, body = post.call_args.args[1], post.call_args.args[2]
        self.assertEqual(
            (path, body["days"], body["leave_type"]), ("hr/leave-usages", 2, "ANNUAL")
        )
        self.assertEqual(body["source_request_id"], request_id)

    def test_access_completion_grants_role_in_itsm(self):
        with patch.object(
            ext.client, "post", return_value={"status": "GRANTED"}
        ) as post:
            out = ext.on_completed(
                _cursor(),
                request_id=str(uuid4()),
                type_code="ACCESS",
                payload={"requested_role": "AWS_READONLY", "duration_days": 30},
                requester_id=str(uuid4()),
            )
        self.assertEqual(post.call_args.args[1], "it/user-access")
        self.assertEqual(out["it_access"]["status"], "GRANTED")


class TaxonomyTests(SimpleTestCase):
    MIGRATION = ROOT / "database/migrations/17_external_systems_via_api.sql"

    def _migration_mapping(self):
        sql = self.MIGRATION.read_text(encoding="utf-8")
        block = sql[
            sql.index("UPDATE eas.request_type rt SET category = m.grp") : sql.index(
                ") AS m(code, grp)"
            )
        ]
        return dict(re.findall(r"\('([A-Z_]+)','([A-Z_]+)'\)", block))

    def test_seed_catalogue_matches_migration_groups(self):
        catalogue = json.loads(
            (ROOT / "api_core/catalog/catalog_v2.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {i["code"]: i["category"] for i in catalogue["items"]},
            self._migration_mapping(),
        )
        self.assertEqual(len(catalogue["groups"]), 12)

    def test_absence_group_has_the_owner_example(self):
        sql = self.MIGRATION.read_text(encoding="utf-8")
        for label in ("Đi muộn", "Về sớm", "Nghỉ phép có lương", "Nghỉ không lương"):
            self.assertIn(f"'{label}'", sql)
        self.assertEqual(self._migration_mapping()["BUSINESS_TRIP"], "ABSENCE")


class FieldLabelTests(SimpleTestCase):
    def test_plan_labels_are_not_hidden_by_catalog_v2_item(self):
        # catalog_v2 items carry no field_labels; an `a or b` chain used to
        # return {} and every WFH field showed as "Thông tin bổ sung".
        from api_core.catalog.views import resolve_field_labels

        labels = resolve_field_labels("WFH_REQ")
        self.assertEqual(labels["task_list"], "Danh sách công việc")
        self.assertEqual(labels["communication_channel"], "Kênh liên lạc")
        self.assertIn("leave_kind", resolve_field_labels("LEAVE"))
