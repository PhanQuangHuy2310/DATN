"""AI policy rule versions stored in eas.ai_policy_version (source of truth).

The AI service only caches the active document: every activation is pushed
to it, and an AI container that starts without a cache pulls the active
version through the internal endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow.service import CommandError, _append_admin_audit

logger = logging.getLogger(__name__)

RULE_KEYS = {
    "id",
    "description",
    "request_type",
    "amount_gt",
    "days_gt",
    "min_risk",
    "auto_approve",
}
SELECT_COLUMNS = """
    id::text, version, document, state, created_at, activated_at,
    (SELECT display_name FROM eas.app_user WHERE id = created_by)
"""


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    )


def validate_document(body: Any) -> dict[str, Any]:
    """Mirror of the AI service PolicyDocument schema, checked before storing."""
    if not isinstance(body, dict) or not {"version", "rules"} <= set(body) <= {
        "version",
        "rules",
        "activate",
    }:
        raise CommandError("INVALID_POLICY_RULES", status=422)
    version, rules = body["version"], body["rules"]
    if not isinstance(version, str) or not 1 <= len(version.strip()) <= 50:
        raise CommandError("INVALID_POLICY_VERSION", status=422)
    if not isinstance(rules, list) or len(rules) > 200:
        raise CommandError("INVALID_POLICY_RULES", status=422)
    seen = set()
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or set(rule) - RULE_KEYS
            or not isinstance(rule.get("id"), str)
            or not 1 <= len(rule["id"]) <= 50
            or rule["id"] in seen
        ):
            raise CommandError("INVALID_POLICY_RULES", status=422)
        seen.add(rule["id"])
        min_risk = rule.get("min_risk")
        auto = rule.get("auto_approve")
        if (
            (
                min_risk is not None
                and (
                    not isinstance(min_risk, int)
                    or isinstance(min_risk, bool)
                    or not 1 <= min_risk <= 5
                )
            )
            or (auto is not None and not isinstance(auto, bool))
            or (min_risk is None and auto is None)
            or any(
                rule.get(key) is not None and not _number(rule[key])
                for key in ("amount_gt", "days_gt")
            )
            or (
                rule.get("request_type") is not None
                and not isinstance(rule["request_type"], str)
            )
        ):
            raise CommandError("INVALID_POLICY_RULES", status=422)
    return {"version": version.strip(), "rules": rules}


def _serialize(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "version": row[1],
        "rules": row[2].get("rules", []),
        "state": row[3],
        "created_at": row[4].isoformat() if row[4] else None,
        "activated_at": row[5].isoformat() if row[5] else None,
        "created_by": row[6],
    }


def list_versions(*, limit: int = 50) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(  # NOSONAR python:S2077 - SELECT_COLUMNS is a constant fragment
            f"SELECT {SELECT_COLUMNS} FROM eas.ai_policy_version "
            "ORDER BY created_at DESC LIMIT %s",
            [limit],
        )
        return {"items": [_serialize(row) for row in cursor.fetchall()]}


def active_document() -> dict[str, Any] | None:
    """Policy the AI must run: the last applied learning result (regulation
    rules + manual rules, migration 12), else the active manual version."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass('eas.ai_learning_job') IS NOT NULL, "
            "to_regclass('eas.ai_policy_version') IS NOT NULL"
        )
        learning_ready, manual_ready = cursor.fetchone()
        if learning_ready is True:
            cursor.execute(
                "SELECT applied_policy FROM eas.ai_system_state WHERE id = 1"
            )
            row = cursor.fetchone()
            if row and row[0] and row[0].get("version"):
                return {"version": row[0]["version"], "rules": row[0].get("rules", [])}
        if manual_ready is not True:
            return None
        cursor.execute(
            "SELECT version, document FROM eas.ai_policy_version WHERE state = 'ACTIVE'"
        )
        row = cursor.fetchone()
    return {"version": row[0], "rules": row[1].get("rules", [])} if row else None


def _activate(cursor, *, actor: Actor, version_id: str, correlation_id: str) -> None:
    cursor.execute(
        "UPDATE eas.ai_policy_version SET state='INACTIVE' WHERE state='ACTIVE' AND id<>%s",
        [version_id],
    )
    cursor.execute(
        """
        UPDATE eas.ai_policy_version
        SET state='ACTIVE', activated_by=%s, activated_at=statement_timestamp()
        WHERE id=%s RETURNING version
        """,
        [actor.id, version_id],
    )
    row = cursor.fetchone()
    if not row:
        raise CommandError("NOT_FOUND", status=404)
    _append_admin_audit(
        cursor,
        actor_id=actor.id,
        action="AI_POLICY_ACTIVATED",
        target_type="ai_policy_version",
        target_id=version_id,
        details={"version": row[0]},
        reason=f"Kích hoạt bộ luật AI {row[0]}",
        correlation_id=correlation_id,
    )


def publish_version(*, actor: Actor, body: Any, correlation_id: str) -> dict[str, Any]:
    document = validate_document(body)
    activate = body.get("activate", True) is not False
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM eas.ai_policy_version WHERE version=%s",
            [document["version"]],
        )
        if cursor.fetchone():
            raise CommandError("POLICY_VERSION_EXISTS", status=409)
        cursor.execute(
            """
            INSERT INTO eas.ai_policy_version(version, document, created_by)
            VALUES (%s, %s, %s) RETURNING id::text
            """,
            [document["version"], Jsonb(document), actor.id],
        )
        version_id = cursor.fetchone()[0]
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="AI_POLICY_CREATED",
            target_type="ai_policy_version",
            target_id=version_id,
            details={"version": document["version"], "rules": len(document["rules"])},
            reason=f"Nạp bộ luật AI {document['version']}",
            correlation_id=correlation_id,
        )
        if activate:
            _activate(
                cursor,
                actor=actor,
                version_id=version_id,
                correlation_id=correlation_id,
            )
    return {"id": version_id, "activated": activate, **document}


def activate_version(
    *, actor: Actor, version_id: str, correlation_id: str
) -> dict[str, Any]:
    with transaction.atomic(), connection.cursor() as cursor:
        _activate(
            cursor, actor=actor, version_id=version_id, correlation_id=correlation_id
        )
    return active_document() or {}


def push_to_ai(document: dict[str, Any], correlation_id: str) -> dict[str, Any] | None:
    """Apply a manual rule change to the AI.

    With migration 12 this queues an AI learning job: the AI merges the manual
    rules with the regulation rules, verifies them, notifies users and only
    then unlocks. Older databases fall back to refreshing the AI cache.
    """
    from api_core.integrations.ai_service import ai_client_sync
    from api_core.workflow import ai_learning

    if ai_learning.jobs_table_ready():
        with transaction.atomic(), connection.cursor() as cursor:
            job_id = ai_learning.enqueue_learning(
                cursor,
                reason=f"Kích hoạt bộ luật AI {document['version']}",
                requested_by=None,
            )
        return {"queued_job": job_id} if job_id else None

    try:
        return ai_client_sync.publish_policy_rules(
            document={"version": document["version"], "rules": document["rules"]},
            correlation_id=correlation_id,
        )
    except RuntimeError:
        logger.warning("AI policy cache not refreshed for %s", document["version"])
        return None
