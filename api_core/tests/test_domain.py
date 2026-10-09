from datetime import date
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.domain import (
    PayloadValidationError,
    RoutingError,
    resolve_route,
    validate_payload,
)


class PayloadValidationTests(SimpleTestCase):
    def setUp(self):
        self.requester = str(uuid4())
        self.handover = str(uuid4())
        self.schema = {
            "schema_version": 1,
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 5, "maxLength": 150},
                "reason": {"type": "string", "minLength": 10, "maxLength": 2000},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "handover_user_id": {"type": "string", "format": "uuid"},
            },
            "required": [
                "title",
                "reason",
                "start_date",
                "end_date",
                "handover_user_id",
            ],
            "additionalProperties": False,
        }

    def test_normalizes_valid_leave_payload(self):
        result = validate_payload(
            type_code="LEAVE",
            payload={
                "title": "  Xin nghỉ phép  ",
                "reason": "Giải quyết việc gia đình",
                "start_date": "2026-10-10",
                "end_date": "2026-10-12",
                "handover_user_id": self.handover,
            },
            form_schema=self.schema,
            requester_id=self.requester,
            today=date(2026, 10, 9),
        )
        self.assertEqual(result["title"], "Xin nghỉ phép")

    def test_rejects_unknown_html_past_and_self_handover(self):
        with self.assertRaises(PayloadValidationError) as raised:
            validate_payload(
                type_code="LEAVE",
                payload={
                    "title": "<b>Nghỉ</b>",
                    "reason": "Giải quyết việc gia đình",
                    "start_date": "2026-10-08",
                    "end_date": "2026-10-07",
                    "handover_user_id": self.requester,
                    "owner_id": self.requester,
                },
                form_schema=self.schema,
                requester_id=self.requester,
                today=date(2026, 10, 9),
            )
        errors = raised.exception.errors
        self.assertIn("UNKNOWN_FIELD", errors["owner_id"])
        self.assertIn("HTML_NOT_ALLOWED", errors["title"])
        self.assertIn("REQUESTER_CANNOT_BE_HANDOVER", errors["handover_user_id"])

    def test_leave_range_is_inclusive_at_30_days(self):
        base = {
            "title": "Xin nghỉ phép",
            "reason": "Giải quyết việc gia đình",
            "start_date": "2026-10-10",
            "handover_user_id": self.handover,
        }
        accepted = validate_payload(
            type_code="LEAVE",
            payload={**base, "end_date": "2026-11-08"},
            form_schema=self.schema,
            requester_id=self.requester,
            today=date(2026, 10, 9),
        )
        self.assertEqual(accepted["end_date"], "2026-11-08")

        with self.assertRaises(PayloadValidationError) as raised:
            validate_payload(
                type_code="LEAVE",
                payload={**base, "end_date": "2026-11-09"},
                form_schema=self.schema,
                requester_id=self.requester,
                today=date(2026, 10, 9),
            )
        self.assertIn("RANGE_EXCEEDS_30_DAYS", raised.exception.errors["end_date"])

    def test_self_handover_cannot_bypass_uuid_canonicalization(self):
        with self.assertRaises(PayloadValidationError) as raised:
            validate_payload(
                type_code="LEAVE",
                payload={
                    "title": "Xin nghỉ phép",
                    "reason": "Giải quyết việc gia đình",
                    "start_date": "2026-10-10",
                    "end_date": "2026-10-11",
                    "handover_user_id": self.requester.upper(),
                },
                form_schema=self.schema,
                requester_id=self.requester,
                today=date(2026, 10, 9),
            )
        self.assertIn(
            "REQUESTER_CANNOT_BE_HANDOVER", raised.exception.errors["handover_user_id"]
        )

    def test_rejects_schema_that_allows_unknown_fields(self):
        self.schema["additionalProperties"] = True
        with self.assertRaises(PayloadValidationError) as raised:
            validate_payload(
                type_code="LEAVE",
                payload={},
                form_schema=self.schema,
                requester_id=self.requester,
                today=date(2026, 10, 9),
            )
        self.assertIn("UNSUPPORTED_SCHEMA", raised.exception.errors["$schema"])

    def test_rejects_malformed_property_schema_before_payload_evaluation(self):
        self.schema["properties"]["title"]["minLength"] = "five"
        self.schema["properties"]["reason"]["enum"] = "not-a-list"
        with self.assertRaises(PayloadValidationError) as raised:
            validate_payload(
                type_code="LEAVE",
                payload={},
                form_schema=self.schema,
                requester_id=self.requester,
                today=date(2026, 10, 9),
            )
        errors = raised.exception.errors["$schema"]
        self.assertIn("title:INVALID_LENGTH_BOUNDS", errors)
        self.assertIn("reason:INVALID_ENUM", errors)


class RoutingTests(SimpleTestCase):
    def setUp(self):
        self.department = str(uuid4())
        self.requester = str(uuid4())
        self.manager = str(uuid4())
        self.finance = str(uuid4())
        self.director = str(uuid4())
        self.executor = str(uuid4())
        self.bindings = {
            "schema_version": 1,
            "departments": {
                self.department: {
                    "FINANCE": self.finance,
                    "DIRECTOR": self.director,
                    "EXECUTOR_ASSET": self.executor,
                }
            },
        }
        self.rules = {
            "schema_version": 1,
            "rules": [
                {
                    "id": "HIGH",
                    "priority": 10,
                    "when": {"amount_gt": 50_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE", "DIRECTOR"],
                },
                {
                    "id": "MID",
                    "priority": 20,
                    "when": {"amount_gte": 10_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE"],
                },
                {"id": "LOW", "default": True, "approvers": ["DIRECT_MANAGER"]},
            ],
            "executor": "EXECUTOR_ASSET",
            "acceptor": "REQUESTER",
        }

    def resolve(self, amount):
        return resolve_route(
            route_rules=self.rules,
            actor_bindings=self.bindings,
            department_id=self.department,
            requester_id=self.requester,
            manager_id=self.manager,
            amount_vnd=amount,
        )

    def test_equipment_thresholds(self):
        self.assertEqual(self.resolve(9_999_999).matched_rule_id, "LOW")
        self.assertEqual(self.resolve(10_000_000).matched_rule_id, "MID")
        self.assertEqual(self.resolve(50_000_000).matched_rule_id, "MID")
        self.assertEqual(self.resolve(50_000_001).matched_rule_id, "HIGH")

    def test_route_snapshot_shape(self):
        route = self.resolve(50_000_001).resolved_route
        self.assertEqual([item["step_no"] for item in route], [1, 2, 3])
        self.assertEqual(route[0]["resolver"], "DIRECT_MANAGER")

    def test_rejects_separation_of_duties_violation(self):
        self.bindings["departments"][self.department]["EXECUTOR_ASSET"] = self.manager
        with self.assertRaises(RoutingError):
            self.resolve(1)

    def test_requester_cannot_resolve_as_executor(self):
        self.bindings["departments"][self.department]["EXECUTOR_ASSET"] = self.requester
        with self.assertRaisesRegex(RoutingError, "execute own"):
            self.resolve(1)

    def test_rejects_operator_not_supported_by_database_contract(self):
        self.rules["rules"][0]["when"] = {"amount_eq": 50_000_001}
        with self.assertRaisesRegex(RoutingError, "Unsupported route operator"):
            self.resolve(50_000_001)

    def test_rejects_fractional_and_negative_route_thresholds(self):
        for invalid_threshold in (10.5, -1):
            with self.subTest(threshold=invalid_threshold):
                self.rules["rules"][0]["when"] = {"amount_gt": invalid_threshold}
                with self.assertRaisesRegex(RoutingError, "integer VND"):
                    self.resolve(50_000_001)

    def test_rejects_default_that_is_not_final(self):
        default = self.rules["rules"].pop()
        self.rules["rules"].insert(0, default)
        with self.assertRaisesRegex(RoutingError, "final default"):
            self.resolve(1)

    def test_rejects_duplicate_rule_ids_and_unknown_actor_slots(self):
        self.rules["rules"][1]["id"] = self.rules["rules"][0]["id"]
        with self.assertRaisesRegex(RoutingError, "IDs"):
            self.resolve(10_000_000)

        self.rules["rules"][1]["id"] = "MID"
        self.rules["rules"][2]["approvers"] = ["CEO_FROM_FREE_TEXT"]
        with self.assertRaisesRegex(RoutingError, "allowed slots"):
            self.resolve(1)
