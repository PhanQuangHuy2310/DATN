"""Regression tests for the owner's B3/B4/C1/C2/C3/C4/A3 decisions and repairs."""

from __future__ import annotations

import os
import re
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError as DjangoCommandError
from django.db import DatabaseError
from django.test import SimpleTestCase

from api_core import worker
from api_core.ai_client import OcrUnavailableError
from api_core.authn.models import Actor
from api_core.catalog.thesis_core_types import THESIS_CORE_CODES, THESIS_CORE_TYPES
from api_core.domain import resource_guard as rg
from api_core.domain.approval_policy import apply_purchasing_ladder, describe_rules
from api_core.domain.validation import allowed_reminder_fractions
from api_core.management.commands import repair_workflow_data as repair
from api_core.workflow import delegation_service as ds
from api_core.workflow import resource_guard as rga
from api_core.workflow.service import CommandError

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)


def _id() -> str:
    return str(uuid4())


def _actor(*roles: str) -> Actor:
    return Actor(
        id=_id(),
        email="person@eas.com",
        display_name="Person",
        department_id=_id(),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


class _DbPatchedTestCase(SimpleTestCase):
    # Lets SimpleTestCase tests replace connection.cursor safely.
    databases: ClassVar[set[str]] = {"default"}


# --------------------------------------------------------------------------- B4
class OutboxRetryTests(_DbPatchedTestCase):
    def setUp(self):
        worker._max_attempts_cache = None
        self.addCleanup(setattr, worker, "_max_attempts_cache", None)

    def test_backoff_follows_thesis_schedule(self):
        self.assertEqual(
            [worker.retry_delay(n).total_seconds() for n in range(1, 7)],
            [10, 30, 60, 300, 300, 300],
        )

    def _limit(self, definition):
        worker._max_attempts_cache = None
        cursor = MagicMock()
        cursor.fetchone.return_value = (definition,)
        return worker.outbox_max_attempts(cursor)

    def test_limit_follows_database_constraint(self):
        self.assertEqual(self._limit("CHECK ((state <> 'DEAD') OR (attempts = 4))"), 4)
        self.assertEqual(
            self._limit(
                "CHECK (((state) <> 'DEAD') OR ((attempts >= 4) AND (attempts <= 6)))"
            ),
            6,
        )
        self.assertEqual(self._limit(""), 4)

    def test_migration_09_matches_worker_detection(self):
        sql = (
            ROOT
            / "database/report_migrations/09_outbox_six_attempts_DBA_REVIEW_ONLY.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("attempts >= 4 AND attempts <= 6", sql)
        self.assertIn("ROLLBACK", sql)

    def test_dead_only_after_six_attempts_when_migrated(self):
        worker._max_attempts_cache = 6
        cursor = MagicMock()
        cursor.rowcount = 1
        with (
            patch.object(worker.transaction, "atomic", return_value=nullcontext()),
            patch.object(worker.connection, "cursor") as conn,
        ):
            conn.return_value.__enter__.return_value = cursor
            for attempts, state in ((5, "PENDING"), (6, "DEAD")):
                item = worker.OutboxItem("e", None, "X", {}, attempts, "lease")
                worker.fail_outbox(item, RuntimeError("x"))
                self.assertEqual(cursor.execute.call_args.args[1][0], state)


# --------------------------------------------------------------------------- B3
class SlaRecipientsTests(_DbPatchedTestCase):
    def _item(self, event_type):
        return worker.OutboxItem("e", "r", event_type, {"stage_id": "s"}, 1, "lease")

    def test_l2_recipients_are_metadata_only_with_request_code(self):
        cursor = MagicMock()
        director, ops = _id(), _id()
        cursor.fetchall.return_value = [(director,), (ops,)]
        cursor.fetchone.return_value = ("REQ-2026-0001",)
        recipients = worker._recipients(cursor, self._item("SLA_ESCALATE"))
        self.assertEqual([r.user_id for r in recipients], [director, ops])
        self.assertTrue(all(r.metadata_only for r in recipients))
        self.assertIn("REQ-2026-0001", recipients[0].label)

    def test_l1_head_is_metadata_only_and_assignee_is_not(self):
        cursor = MagicMock()
        assignee, head = _id(), _id()
        cursor.fetchone.side_effect = [(assignee,), (head,), ("REQ-1",)]
        with patch.dict(os.environ, {"EAS_SLA_ESCALATION_LEVELS": "1"}):
            recipients = worker._recipients(cursor, self._item("SLA_BREACH"))
        self.assertEqual(
            [(r.user_id, r.metadata_only) for r in recipients],
            [(assignee, False), (head, True)],
        )

    def _acknowledge(self, recipient, can_read):
        cursor = MagicMock()
        cursor.rowcount = 1
        cursor.fetchone.side_effect = [("PROCESSING", "lease", True), (True, can_read)]
        with (
            patch.object(worker.transaction, "atomic", return_value=nullcontext()),
            patch.object(worker.connection, "cursor") as conn,
            patch.object(worker, "_recipients", return_value=[recipient]),
            patch.object(worker, "_append_admin_audit") as audit,
        ):
            conn.return_value.__enter__.return_value = cursor
            worker.acknowledge_outbox(self._item("SLA_ESCALATE"))
        inserted = any(
            "INSERT INTO eas.notification" in c.args[0]
            for c in cursor.execute.call_args_list
        )
        return inserted, audit.called

    def test_metadata_only_recipient_is_notified_without_read_access(self):
        self.assertEqual(
            self._acknowledge(worker.Recipient(_id(), "SLA L2", True), False),
            (True, False),
        )

    def test_normal_recipient_without_read_access_is_still_skipped(self):
        self.assertEqual(
            self._acknowledge(worker.Recipient(_id(), "x", False), False),
            (False, True),
        )

    def test_reminder_fraction_080_only_after_migration_flag(self):
        with patch.dict(os.environ, {"EAS_SLA_ESCALATION_LEVELS": ""}):
            self.assertEqual(allowed_reminder_fractions(), (0.5,))
        with patch.dict(os.environ, {"EAS_SLA_ESCALATION_LEVELS": "1"}):
            self.assertEqual(allowed_reminder_fractions(), (0.8, 0.5))


# --------------------------------------------------------------------------- C3
class DelegationServiceTests(SimpleTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"EAS_APPROVAL_DELEGATION": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.actor = _actor("APPROVER")
        self.delegate = _id()
        start = datetime.now(timezone.utc) + timedelta(hours=1)
        self.body = {
            "delegate_id": self.delegate,
            "valid_from": start.isoformat(),
            "valid_to": (start + timedelta(days=5)).isoformat(),
            "reason": "Đi công tác nước ngoài một tuần",
        }

    def _create(self, cursor, body=None, actor=None, ops=False):
        def run(**kwargs):
            body_, status, _ = kwargs["operation"](cursor)
            return body_, status

        with (
            patch.object(ds, "_execute_idempotent", side_effect=run),
            patch.object(ds, "_append_admin_audit") as audit,
        ):
            result = ds.create_delegation(
                actor=actor or self.actor,
                body=body or self.body,
                idempotency_key=_id(),
                correlation_id=_id(),
                ops=ops,
            )
        return result, audit

    def _cursor(self, covers=(True, True), overlap=False, chain=False):
        cursor = MagicMock()
        row = (
            _id(),
            self.actor.id,
            "A",
            self.delegate,
            "B",
            None,
            None,
            None,
            None,
            NOW,
            NOW + timedelta(days=1),
            "r",
            "SCHEDULED",
            self.actor.id,
            NOW,
            None,
            None,
        )
        cursor.fetchall.return_value = [(self.actor.id,), (self.delegate,)]
        cursor.fetchone.side_effect = [
            (covers[0],),
            (covers[1],),
            (overlap, chain),
            ("new-id",),
            row,
        ]
        return cursor

    def test_disabled_until_migration_flag(self):
        with (
            patch.dict(os.environ, {"EAS_APPROVAL_DELEGATION": ""}),
            self.assertRaises(CommandError) as raised,
        ):
            ds.list_delegations(self.actor, {}, ops=False)
        self.assertEqual(raised.exception.code, "DELEGATION_NOT_ENABLED")

    def test_create_records_audit_and_notifies_both_parties(self):
        cursor = self._cursor()
        (body, status), audit = self._create(cursor)
        self.assertEqual(status, 201)
        self.assertEqual(body["delegation"]["status"], "SCHEDULED")
        self.assertEqual(
            audit.call_args.kwargs["action"], "APPROVAL_DELEGATION_CREATED"
        )
        outbox = [
            c for c in cursor.execute.call_args_list if "outbox_event" in c.args[0]
        ]
        self.assertEqual(outbox[0].args[1][0], "DELEGATION_CREATED")
        locks = cursor.execute.call_args_list[1].args[0]
        self.assertIn("FOR UPDATE", locks)

    def test_rejects_self_past_start_and_inverted_period(self):
        for change, code in (
            ({"delegate_id": self.actor.id}, "DELEGATION_SELF"),
            (
                {"valid_from": (NOW - timedelta(days=30)).isoformat()},
                "DELEGATION_START_IN_PAST",
            ),
            ({"valid_to": self.body["valid_from"]}, "DELEGATION_PERIOD_INVALID"),
        ):
            with self.assertRaises(CommandError) as raised:
                self._create(MagicMock(), {**self.body, **change})
            self.assertEqual(raised.exception.code, code)

    def test_permission_overlap_and_chain_are_enforced(self):
        for kwargs, code in (
            ({"covers": (False, True)}, "DELEGATOR_NOT_APPROVER"),
            ({"covers": (True, False)}, "DELEGATE_NOT_ELIGIBLE"),
            ({"overlap": True}, "DELEGATION_OVERLAP"),
            ({"chain": True}, "DELEGATION_CHAIN_FORBIDDEN"),
        ):
            with self.assertRaises(CommandError) as raised:
                self._create(self._cursor(**kwargs))
            self.assertEqual(raised.exception.code, code)

    def test_eligibility_sql_excludes_admins_and_covers_whole_period(self):
        self.assertIn("'OPS_ADMIN', 'POLICY_ADMIN', 'AUDITOR'", ds.SQL_APPROVER_COVERS)
        self.assertIn("rm.valid_to >= %s", ds.SQL_APPROVER_COVERS)

    def test_ops_admin_cannot_be_a_party(self):
        ops = _actor("OPS_ADMIN")
        with self.assertRaises(CommandError) as raised:
            self._create(
                MagicMock(), {**self.body, "delegator_id": ops.id}, actor=ops, ops=True
            )
        self.assertEqual(raised.exception.code, "DELEGATION_ADMIN_PARTY")

    def test_only_delegator_or_ops_may_revoke(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(_id(), self.delegate, None, None, False, False)]
        with (
            patch.object(
                ds,
                "_execute_idempotent",
                side_effect=lambda **k: k["operation"](cursor),
            ),
            self.assertRaises(CommandError) as raised,
        ):
            ds.revoke_delegation(
                actor=self.actor,
                body={"reason": "Không còn cần ủy quyền"},
                idempotency_key=_id(),
                correlation_id=_id(),
                delegation_id=_id(),
            )
        self.assertEqual(raised.exception.code, "FORBIDDEN")

    @patch("api_core.authn.service.load_actor_from_session")
    def test_portal_separation(self, load_actor):
        load_actor.return_value = _actor("OPS_ADMIN", "APPROVER")
        response = self.client.get("/api/v1/delegations")
        self.assertEqual(response.json()["error"]["code"], "ADMIN_PORTAL_ONLY")
        load_actor.return_value = _actor("APPROVER")
        self.assertEqual(self.client.get("/api/v1/ops/delegations").status_code, 403)


# --------------------------------------------------------------------------- C2
class ResourceGuardTests(SimpleTestCase):
    def _eval(self, balance, requested="3", reserved="0", mode="enforce"):
        return rg.evaluate(
            kind="LEAVE",
            requested=Decimal(requested),
            balance=balance,
            reserved=Decimal(reserved),
            now=NOW,
            max_age=timedelta(hours=24),
            mode=mode,
        )

    def _bal(self, available="5", age_hours=1, authoritative=True):
        return rg.Balance(
            "mock_hr.leave_balance",
            Decimal(available),
            NOW - timedelta(hours=age_hours),
            authoritative,
        )

    def test_confirmed_shortage_blocks_only_in_enforce_mode(self):
        result = self._eval(self._bal(), requested="4", reserved="2")
        self.assertEqual((result.status, result.blocking), ("INSUFFICIENT", True))
        self.assertIn("Không đủ ngày phép", result.message)
        self.assertIn("đang chờ xử lý 2 ngày", result.message)
        advisory = self._eval(self._bal(), requested="4", reserved="2", mode="advisory")
        self.assertFalse(advisory.blocking)

    def test_unverified_sources_never_block(self):
        cases = (
            (None, "NO_LINKED_RECORD"),
            (self._bal(age_hours=48), "STALE"),
            (self._bal(authoritative=False), "SOURCE_NOT_AUTHORITATIVE"),
        )
        for balance, reason in cases:
            result = self._eval(balance, requested="99")
            self.assertEqual((result.status, result.reason), ("UNVERIFIED", reason))
            self.assertFalse(result.blocking)

    def test_sufficient_balance(self):
        self.assertEqual(self._eval(self._bal(), requested="5").status, "OK")

    def test_mock_sources_are_not_authoritative_by_default(self):
        with patch.dict(os.environ, {"EAS_RESOURCE_AUTHORITATIVE_SOURCES": ""}):
            self.assertEqual(rga.authoritative_sources(), frozenset())

    def test_unreadable_source_is_reported_not_raised(self):
        cursor = MagicMock()
        cursor.execute.side_effect = DatabaseError("permission denied")
        with (
            patch.object(rga.transaction, "atomic", return_value=nullcontext()),
            patch.dict(os.environ, {"EAS_RESOURCE_GUARD": "enforce"}),
        ):
            results = rga.check_resources(
                cursor,
                actor_id=_id(),
                department_id=_id(),
                type_code="LEAVE",
                payload={"start_date": "2026-11-10", "end_date": "2026-11-12"},
                amount=None,
                lock=True,
            )
        self.assertEqual(
            [(r.kind, r.reason) for r in results], [("LEAVE", "SOURCE_UNAVAILABLE")]
        )

    def test_off_mode_does_nothing(self):
        with patch.dict(os.environ, {"EAS_RESOURCE_GUARD": "off"}):
            self.assertEqual(
                rga.check_resources(
                    MagicMock(),
                    actor_id=_id(),
                    department_id=_id(),
                    type_code="EQUIPMENT",
                    payload={},
                    amount=1,
                ),
                [],
            )


# --------------------------------------------------------------------------- A3
class ApprovalLadderTests(SimpleTestCase):
    def _rules(self, rules):
        return {"schema_version": 1, "rules": rules, "executor": None, "acceptor": None}

    def test_equipment_mid_tier_moves_to_5m(self):
        current = self._rules(
            [
                {
                    "id": "H",
                    "priority": 10,
                    "when": {"amount_gt": 50_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE", "DIRECTOR"],
                },
                {
                    "id": "M",
                    "priority": 20,
                    "when": {"amount_gte": 10_000_000},
                    "approvers": ["DIRECT_MANAGER", "FINANCE"],
                },
                {"id": "D", "default": True, "approvers": ["DIRECT_MANAGER"]},
            ]
        )
        self.assertEqual(
            describe_rules(apply_purchasing_ladder(current)),
            [
                "amount_gt 50000000: DIRECT_MANAGER → FINANCE → DIRECTOR",
                "amount_gte 5000000: DIRECT_MANAGER → FINANCE",
                "mặc định: DIRECT_MANAGER",
            ],
        )

    def test_stricter_default_is_never_weakened_and_other_rules_kept(self):
        current = self._rules(
            [
                {
                    "id": "APP",
                    "priority": 5,
                    "when": {"app_code_in": ["ERP"]},
                    "approvers": ["DIRECT_MANAGER", "CTO"],
                },
                {
                    "id": "D",
                    "default": True,
                    "approvers": ["DIRECT_MANAGER", "PROCUREMENT_MANAGER", "FINANCE"],
                },
            ]
        )
        result = apply_purchasing_ladder(current)
        described = describe_rules(result)
        self.assertEqual(
            described[-1], "mặc định: DIRECT_MANAGER → PROCUREMENT_MANAGER → FINANCE"
        )
        self.assertIn(
            "amount_gt 50000000: DIRECT_MANAGER → PROCUREMENT_MANAGER → FINANCE → DIRECTOR",
            described,
        )
        self.assertTrue(any("app_code_in" in d for d in described))
        priorities = [r["priority"] for r in result["rules"] if not r.get("default")]
        self.assertEqual(len(priorities), len(set(priorities)))


# --------------------------------------------------------------------------- C1
class ThesisCoreTypesTests(SimpleTestCase):
    def test_ten_distinct_core_types_map_to_existing_catalog_records(self):
        self.assertEqual(len(THESIS_CORE_TYPES), 10)
        self.assertEqual(len(THESIS_CORE_CODES), 10)
        sources = "".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in [
                *(ROOT / "database").rglob("*.sql"),
                *(ROOT / "api_core/catalog").glob("*.json"),
            ]
        )
        for code in THESIS_CORE_CODES:
            self.assertRegex(sources, rf"['\"]{re.escape(code)}['\"]", code)


# --------------------------------------------------------------------------- repair
class RepairCommandTests(_DbPatchedTestCase):
    PLAN: ClassVar[dict] = {
        "admin_grants": [],
        "orphaned_approvals": [],
        "terminal_live_work": [],
    }

    def _run(self, *args):
        out = StringIO()
        with (
            patch.object(repair, "detect", return_value=self.PLAN),
            patch.object(repair.transaction, "atomic", return_value=nullcontext()),
            patch.object(repair.connection, "cursor"),
        ):
            call_command("repair_workflow_data", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing_and_prints_token(self):
        output = self._run()
        self.assertIn("DRY-RUN ONLY", output)
        self.assertIn(repair.plan_token(self.PLAN), output)

    def test_apply_requires_matching_token_and_operator(self):
        with self.assertRaisesRegex(DjangoCommandError, "token mismatch"):
            self._run("--apply", "--confirm", "wrong")
        with self.assertRaisesRegex(DjangoCommandError, "--operator"):
            self._run("--apply", "--confirm", repair.plan_token(self.PLAN))

    def test_token_changes_when_plan_changes(self):
        other = {**self.PLAN, "terminal_live_work": [{"code": "REQ-1"}]}
        self.assertNotEqual(repair.plan_token(self.PLAN), repair.plan_token(other))


# --------------------------------------------------------------------------- C4
class AttachmentOcrTests(_DbPatchedTestCase):
    def _run(self, mime="image/png", side_effect=None, result=None):
        from api_core.workflow import ocr_service

        client = MagicMock()
        client.extract_ocr_from_bytes.side_effect = side_effect
        client.extract_ocr_from_bytes.return_value = result
        cursor = MagicMock()
        cursor.fetchone.return_value = (_id(),)
        with (
            patch.object(
                ocr_service, "download_attachment", return_value=(b"x", "a.png", mime)
            ),
            patch("api_core.integrations.ai_service.ai_client_sync", client),
            patch.object(ocr_service.transaction, "atomic", return_value=nullcontext()),
            patch.object(ocr_service.connection, "cursor") as conn,
            patch.object(ocr_service, "_append_request_audit") as audit,
        ):
            conn.return_value.__enter__.return_value = cursor
            body = ocr_service.run_attachment_ocr(_actor("REQUESTER"), _id(), _id())
        return body, audit

    def test_unavailable_engine_is_an_error_not_a_fake_result(self):
        with self.assertRaises(CommandError) as raised:
            self._run(side_effect=OcrUnavailableError("AI_OCR_HTTP_503"))
        self.assertEqual(
            (raised.exception.code, raised.exception.status), ("OCR_UNAVAILABLE", 503)
        )

    def test_pdf_is_rejected(self):
        with self.assertRaises(CommandError) as raised:
            self._run(mime="application/pdf")
        self.assertEqual(raised.exception.code, "OCR_UNSUPPORTED_TYPE")

    def test_result_is_audited_without_raw_text(self):
        body, audit = self._run(
            result={
                "raw_text": "CÔNG TY ABC MST: 0101234567",
                "extracted_fields": {
                    "amount": 1500000,
                    "tax_code": "0101234567",
                    "junk": 1,
                },
                "confidence": 0.93,
                "engine": "paddleocr",
            }
        )
        details = audit.call_args.kwargs["details"]
        self.assertEqual(audit.call_args.kwargs["action"], "AI_OCR_RECORDED")
        self.assertEqual(
            details["extracted_fields"], {"tax_code": "0101234567", "amount": 1500000}
        )
        self.assertNotIn("raw_text", details)
        self.assertEqual(body["ocr"]["confidence"], 0.93)
