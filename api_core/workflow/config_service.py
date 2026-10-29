from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from django.db import connection
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256
from api_core.authn.service import Actor
from api_core.domain.validation import validate_config_release_payload
from api_core.workflow.constants import ERR_VERSION_CONFLICT
from api_core.workflow.policy_helpers import initial_policy_draft, role_grant_errors
from api_core.workflow.service import (
    CommandError,
    CommandResult,
    _append_admin_audit,
    _execute_idempotent,
)

_HTML_RE = re.compile(r"<[^>]+>")
_SQL_LOCK_SECURITY = "SELECT eas.lock_security(false)"


def _clean_reason(value: Any, default: str = "Published configuration release.") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise CommandError("REASON_INVALID", status=422)
    cleaned = value.strip()
    if len(cleaned) < 10 or len(cleaned) > 2000 or _HTML_RE.search(cleaned):
        raise CommandError("REASON_INVALID", status=422)
    return cleaned


def _uuid_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)
    try:
        return str(UUID(val))
    except (ValueError, TypeError):
        raise CommandError(f"INVALID_{field_name.upper()}", status=422)


def _check_policy_admin(cursor, actor_id: str, type_id: str | None = None) -> None:
    if type_id is None:
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM eas.role_membership
              WHERE user_id = %s AND role = 'POLICY_ADMIN' AND revoked_at IS NULL
                AND valid_from <= statement_timestamp()
                AND (valid_to IS NULL OR valid_to > statement_timestamp())
            )
            """,
            [actor_id],
        )
    else:
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM eas.role_membership
              WHERE user_id = %s AND role = 'POLICY_ADMIN' AND revoked_at IS NULL
                AND valid_from <= statement_timestamp()
                AND (valid_to IS NULL OR valid_to > statement_timestamp())
                AND (type_scope = 'ALL' OR type_id = %s)
            )
            """,
            [actor_id, type_id],
        )
    if not cursor.fetchone()[0]:
        raise CommandError("FORBIDDEN", status=403)


def list_config_releases(
    actor: Actor,
    query_params: dict[str, str],
) -> dict[str, Any]:
    type_code_filter = (query_params.get("type_code") or "").strip() or None
    state_filter = (query_params.get("state") or "").strip() or None

    with connection.cursor() as cursor:
        _check_policy_admin(cursor, actor.id)

        if state_filter and state_filter not in ("DRAFT", "PUBLISHED"):
            raise CommandError("INVALID_STATE_FILTER", status=400)

        cursor.execute(
            """
            SELECT cr.id::text, rt.code, cr.version, cr.state, cr.lifecycle,
                   cr.form_schema, cr.route_rules, cr.actor_bindings, cr.sla_profile,
                   cr.lock_version, cr.content_sha256, cr.created_at, cr.published_at
            FROM eas.config_release cr
            JOIN eas.request_type rt ON rt.id = cr.type_id
            WHERE (%s::text IS NULL OR rt.code = %s)
              AND (%s::text IS NULL OR cr.state = %s)
              AND EXISTS (
                SELECT 1 FROM eas.role_membership rm
                WHERE rm.user_id = %s AND rm.role = 'POLICY_ADMIN' AND rm.revoked_at IS NULL
                  AND rm.valid_from <= statement_timestamp()
                  AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                  AND (rm.type_scope = 'ALL' OR rm.type_id = cr.type_id)
              )
            ORDER BY rt.code, cr.version DESC
            """,
            [type_code_filter, type_code_filter, state_filter, state_filter, actor.id],
        )
        rows = cursor.fetchall()

    items = [
        {
            "id": row[0],
            "type_code": row[1],
            "version": row[2],
            "state": row[3],
            "lifecycle": row[4],
            "form_schema": row[5],
            "route_rules": row[6],
            "actor_bindings": row[7],
            "sla_profile": row[8],
            "lock_version": row[9],
            "content_sha256": row[10],
            "created_at": row[11].isoformat(),
            "published_at": row[12].isoformat() if row[12] else None,
        }
        for row in rows
    ]
    return {"items": items}


def get_config_release(actor: Actor, release_id: str) -> dict[str, Any]:
    norm_id = _uuid_str(release_id, "release_id")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT cr.id::text, rt.code, cr.version, cr.state, cr.lifecycle,
                   cr.form_schema, cr.route_rules, cr.actor_bindings, cr.sla_profile,
                   cr.lock_version, cr.content_sha256, cr.created_at, cr.published_at,
                   cr.type_id::text
            FROM eas.config_release cr
            JOIN eas.request_type rt ON rt.id = cr.type_id
            WHERE cr.id = %s
            """,
            [norm_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("CONFIG_RELEASE_NOT_FOUND", status=404)

        _check_policy_admin(cursor, actor.id, type_id=row[13])

    return {
        "release": {
            "id": row[0],
            "type_code": row[1],
            "version": row[2],
            "state": row[3],
            "lifecycle": row[4],
            "form_schema": row[5],
            "route_rules": row[6],
            "actor_bindings": row[7],
            "sla_profile": row[8],
            "lock_version": row[9],
            "content_sha256": row[10],
            "created_at": row[11].isoformat(),
            "published_at": row[12].isoformat() if row[12] else None,
        }
    }


def policy_actor_options(actor: Actor, type_code: str) -> dict[str, Any]:
    """Only scoped POLICY_ADMIN may see candidates already granted a workflow role.

    This is an editor convenience, never evidence that a future grant remains valid.
    """
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,29}", type_code):
        raise CommandError("UNKNOWN_TYPE_CODE", status=422)
    with connection.cursor() as cursor:
        cursor.execute("SELECT id::text FROM eas.request_type WHERE code=%s", [type_code])
        row = cursor.fetchone()
        if not row:
            raise CommandError("UNKNOWN_TYPE_CODE", status=404)
        type_id = row[0]
        _check_policy_admin(cursor, actor.id, type_id)
        cursor.execute("""
            SELECT d.id::text, d.name FROM eas.department d
            WHERE d.is_active AND EXISTS (
                SELECT 1 FROM eas.role_membership pm
                WHERE pm.user_id=%s AND pm.role='POLICY_ADMIN'
                  AND pm.revoked_at IS NULL
                  AND pm.valid_from<=statement_timestamp()
                  AND (pm.valid_to IS NULL OR pm.valid_to>statement_timestamp())
                  AND (pm.type_scope='ALL' OR (pm.type_scope='ONE' AND pm.type_id=%s))
                  AND (pm.scope_kind='GLOBAL' OR
                       (pm.scope_kind='DEPARTMENT' AND pm.department_id=d.id)))
            ORDER BY d.name, d.id LIMIT 50
        """, [actor.id, type_id])
        departments = cursor.fetchall()
        items = []
        for dept_id, dept_name in departments:
            cursor.execute("""
                SELECT u.id::text,u.display_name, m.role
                FROM eas.role_membership m
                JOIN eas.app_user u ON u.id=m.user_id AND u.is_active
                WHERE m.role IN ('APPROVER','EXECUTOR','ACCEPTOR')
                  AND m.revoked_at IS NULL
                  AND m.valid_from<=statement_timestamp()
                  AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
                  AND (m.type_scope='ALL' OR (m.type_scope='ONE' AND m.type_id=%s))
                  AND (m.scope_kind='GLOBAL' OR
                       (m.scope_kind='DEPARTMENT' AND m.department_id=%s))
                ORDER BY u.display_name,u.id,m.role LIMIT 400
            """, [type_id, dept_id])
            candidate_map = {}
            for user_id, name, role in cursor.fetchall():
                value = candidate_map.setdefault(user_id, {'id':user_id,'name':name,'roles':[]})
                if role not in value['roles']:
                    value['roles'].append(role)
            items.append({'id':dept_id,'name':dept_name,'candidates':list(candidate_map.values())})
    return {'type_code':type_code, 'departments':items}


def list_policy_type_status(actor: Actor) -> dict[str, Any]:
    """POLICY_ADMIN-only, scoped overview of release and requester access.

    No passwords, staff identities or raw role records are returned.
    """
    with connection.cursor() as cursor:
        _check_policy_admin(cursor, actor.id)
        cursor.execute(
            """
            SELECT rt.code, rt.name, rt.lifecycle, rt.is_active,
                   cr.id::text, cr.state,
                   (cr.id IS NOT NULL AND cr.state='PUBLISHED'
                    AND cr.type_id=rt.id AND cr.lifecycle=rt.lifecycle) AS valid_release,
                   (SELECT count(DISTINCT m.user_id)
                    FROM eas.role_membership m
                    JOIN eas.app_user u ON u.id=m.user_id AND u.is_active
                    WHERE m.role='REQUESTER' AND m.revoked_at IS NULL
                      AND m.valid_from<=statement_timestamp()
                      AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
                      AND (m.type_scope='ALL' OR (m.type_scope='ONE' AND m.type_id=rt.id))
                      AND (m.scope_kind='GLOBAL' OR
                           (m.scope_kind='DEPARTMENT' AND m.department_id=u.department_id)))
                      AS requester_count,
                   (SELECT count(*) FROM eas.config_release d
                    WHERE d.type_id=rt.id AND d.state='DRAFT') AS draft_count
            FROM eas.request_type rt
            LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE EXISTS (
                SELECT 1 FROM eas.role_membership m
                WHERE m.user_id=%s AND m.role='POLICY_ADMIN'
                  AND m.revoked_at IS NULL AND m.valid_from<=statement_timestamp()
                  AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
                  AND (m.type_scope='ALL' OR (m.type_scope='ONE' AND m.type_id=rt.id)))
            ORDER BY rt.code
            """, [actor.id]
        )
        rows = cursor.fetchall()
    items = []
    for code, name, lifecycle, is_active, release_id, state, valid, count, drafts in rows:
        blockers = []
        if not is_active: blockers.append('TYPE_INACTIVE')
        if not valid: blockers.append('NO_PUBLISHED_RELEASE')
        if not count: blockers.append('NO_REQUESTER_MEMBERSHIP')
        items.append({"code": code, "name": name, "lifecycle": lifecycle,
                      "is_active": is_active, "active_release_id": release_id if valid else None,
                      "release_state": state, "has_published_release": bool(valid),
                      "requester_count": int(count), "draft_count": int(drafts),
                      "visible_to_some_requesters": not blockers, "route_verified_only_on_submit": True, "blockers": blockers})
    return {"items": items}


def create_or_clone_release(
    *,
    actor: Actor,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    type_code = body.get("type_code")
    if not isinstance(type_code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,29}", type_code):
        raise CommandError("UNKNOWN_TYPE_CODE", status=422)

    clone_from_id = body.get("clone_from_release_id")
    if clone_from_id:
        clone_from_id = _uuid_str(clone_from_id, "clone_from_release_id")

    def _op(cursor) -> tuple[dict[str, Any], int, str | None]:
        cursor.execute(_SQL_LOCK_SECURITY)

        cursor.execute(
            """
            SELECT id::text, lifecycle, active_release_id::text
            FROM eas.request_type
            WHERE code = %s
            FOR UPDATE
            """,
            [type_code],
        )
        rt_row = cursor.fetchone()
        if not rt_row:
            raise CommandError("UNKNOWN_TYPE_CODE", status=404)

        type_id, rt_lifecycle, active_rel_id = rt_row
        _check_policy_admin(cursor, actor.id, type_id=type_id)

        source_id = clone_from_id or active_rel_id
        source_kind = "CLONED_RELEASE" if source_id else "SAFE_STARTER"
        if source_id:
            cursor.execute(
                """
                SELECT form_schema, route_rules, actor_bindings, sla_profile, lifecycle
                FROM eas.config_release
                WHERE id = %s AND type_id = %s
                """,
                [source_id, type_id],
            )
            src = cursor.fetchone()
            if not src:
                raise CommandError("SOURCE_RELEASE_NOT_FOUND_FOR_TYPE", status=404)
            form_schema, route_rules, actor_bindings, sla_profile, lifecycle = src
        else:
            starter = initial_policy_draft(type_code, rt_lifecycle)
            source_kind = starter["source"]
            form_schema = starter["form_schema"]
            route_rules = starter["route_rules"]
            actor_bindings = starter["actor_bindings"]
            sla_profile = starter["sla_profile"]
            lifecycle = rt_lifecycle

        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM eas.config_release WHERE type_id = %s",
            [type_id],
        )
        next_version = cursor.fetchone()[0]

        new_id = str(uuid4())
        cursor.execute(
            """
            INSERT INTO eas.config_release(
              id, type_id, version, state, lifecycle,
              form_schema, route_rules, actor_bindings, sla_profile,
              lock_version, created_by
            ) VALUES (
              %s, %s, %s, 'DRAFT', %s,
              %s, %s, %s, %s,
              0, %s
            )
            """,
            [
                new_id,
                type_id,
                next_version,
                lifecycle,
                Jsonb(form_schema),
                Jsonb(route_rules),
                Jsonb(actor_bindings),
                Jsonb(sla_profile),
                actor.id,
            ],
        )

        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="CONFIG_DRAFT_CREATED",
            target_type="config_release",
            target_id=new_id,
            type_id=type_id,
            details={"version": next_version, "clone_from": source_id},
            reason="Create or clone config release draft.",
            correlation_id=correlation_id,
        )

        return (
            {
                "release": {
                    "id": new_id,
                    "type_code": type_code,
                    "version": next_version,
                    "state": "DRAFT",
                    "lock_version": 0,
                    "draft_source": source_kind,
                }
            },
            201,
            None,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"config:create:{type_code}",
        key=idempotency_key,
        command_body=body,
        operation=_op,
    )


def update_draft_release(
    *,
    actor: Actor,
    release_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    norm_id = _uuid_str(release_id, "release_id")
    expected_version = body.get("expected_version")
    if not isinstance(expected_version, int) or expected_version < 0:
        raise CommandError("INVALID_EXPECTED_VERSION", status=422)

    def _op(cursor) -> tuple[dict[str, Any], int, str | None]:
        cursor.execute(_SQL_LOCK_SECURITY)

        cursor.execute(
            """
            SELECT cr.id::text, cr.type_id::text, cr.state, cr.lock_version,
                   cr.form_schema, cr.route_rules, cr.actor_bindings, cr.sla_profile
            FROM eas.config_release cr
            WHERE cr.id = %s
            FOR UPDATE
            """,
            [norm_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("CONFIG_RELEASE_NOT_FOUND", status=404)

        (
            _r_id,
            type_id,
            state,
            lock_version,
            form_schema,
            route_rules,
            actor_bindings,
            sla_profile,
        ) = row

        _check_policy_admin(cursor, actor.id, type_id=type_id)

        if state == "PUBLISHED":
            raise CommandError("RELEASE_IMMUTABLE", status=409)

        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)

        new_form = body.get("form_schema", form_schema)
        new_routes = body.get("route_rules", route_rules)
        new_actors = body.get("actor_bindings", actor_bindings)
        new_sla = body.get("sla_profile", sla_profile)

        for schema_part, name in (
            (new_form, "form_schema"),
            (new_routes, "route_rules"),
            (new_actors, "actor_bindings"),
            (new_sla, "sla_profile"),
        ):
            if (
                not isinstance(schema_part, dict)
                or schema_part.get("schema_version") != 1
            ):
                raise CommandError("CONFIG_INVALID", status=422, fields=[name])

        cursor.execute(
            """
            UPDATE eas.config_release
            SET form_schema = %s,
                route_rules = %s,
                actor_bindings = %s,
                sla_profile = %s,
                lock_version = lock_version + 1
            WHERE id = %s
            RETURNING lock_version
            """,
            [
                Jsonb(new_form),
                Jsonb(new_routes),
                Jsonb(new_actors),
                Jsonb(new_sla),
                norm_id,
            ],
        )
        new_version = cursor.fetchone()[0]

        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="CONFIG_DRAFT_UPDATED",
            target_type="config_release",
            target_id=norm_id,
            type_id=type_id,
            details={"lock_version": new_version},
            reason="Updated configuration release draft payload.",
            correlation_id=correlation_id,
        )

        return (
            {"release": {"id": norm_id, "lock_version": new_version}},
            200,
            None,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"config:update:{norm_id}",
        key=idempotency_key,
        command_body=body,
        operation=_op,
    )


def validate_release_candidate(*, actor: Actor, release_id: str) -> dict[str, Any]:
    norm_id = _uuid_str(release_id, "release_id")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT cr.id::text, rt.code, cr.type_id::text, cr.lifecycle,
                   cr.form_schema, cr.route_rules, cr.actor_bindings, cr.sla_profile,
                   cr.lock_version
            FROM eas.config_release cr
            JOIN eas.request_type rt ON rt.id = cr.type_id
            WHERE cr.id = %s
            """,
            [norm_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("CONFIG_RELEASE_NOT_FOUND", status=404)

        (
            _r_id,
            _type_code,
            type_id,
            lifecycle,
            form_schema,
            route_rules,
            actor_bindings,
            sla_profile,
            lock_version,
        ) = row

        _check_policy_admin(cursor, actor.id, type_id=type_id)

    errors = validate_config_release_payload(
        lifecycle=lifecycle,
        form_schema=form_schema,
        route_rules=route_rules,
        actor_bindings=actor_bindings,
        sla_profile=sla_profile,
    )
    if _type_code == "RESIGNATION" and not route_rules.get("executor"):
        errors.append("RESIGNATION:executor must be configured for offboarding checklist")
    if _type_code in {"ACCESS_FACILITY","BUSINESS_TRIP","EQUIPMENT_BORROW", "EXPENSE_CLAIM", "IT_SUPPORT", "LEAVE_SPECIAL", "ROOM_BOOKING"} and isinstance(form_schema.get("properties"), dict) and set(form_schema["properties"]) <= {"title","reason"}:
        errors.append("form_schema:define business-specific fields for this request type before publishing")
    if not errors:
        with connection.cursor() as cursor:
            errors.extend(role_grant_errors(cursor, type_id, route_rules, actor_bindings))
    if errors:
        raise CommandError("CONFIG_INVALID", status=422, fields=errors)

    canonical_obj = {
        "actor_bindings": actor_bindings,
        "form_schema": form_schema,
        "lifecycle": lifecycle,
        "route_rules": route_rules,
        "sla_profile": sla_profile,
        "type_id": type_id,
    }
    validation_hash = canonical_sha256(canonical_obj)

    return {
        "valid": True,
        "validation_hash": validation_hash,
        "lock_version": lock_version,
    }


def publish_config_release(
    *,
    actor: Actor,
    release_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    correlation_id: str,
) -> CommandResult:
    norm_id = _uuid_str(release_id, "release_id")
    expected_version = body.get("expected_version")
    if not isinstance(expected_version, int) or expected_version < 0:
        raise CommandError("INVALID_EXPECTED_VERSION", status=422)

    val_hash = body.get("validation_hash")
    reason = _clean_reason(
        body.get("reason"), default="Published configuration release."
    )

    def _op(cursor) -> tuple[dict[str, Any], int, str | None]:
        cursor.execute(_SQL_LOCK_SECURITY)

        cursor.execute(
            """
            SELECT cr.id::text, rt.id::text, rt.code, cr.version, cr.state,
                   cr.lifecycle, cr.form_schema, cr.route_rules, cr.actor_bindings,
                   cr.sla_profile, cr.lock_version
            FROM eas.request_type rt
            JOIN eas.config_release cr ON cr.type_id = rt.id
            WHERE cr.id = %s
            FOR UPDATE OF rt, cr
            """,
            [norm_id],
        )
        row = cursor.fetchone()
        if not row:
            raise CommandError("CONFIG_RELEASE_NOT_FOUND", status=404)

        (
            _rel_id,
            type_id,
            type_code,
            version,
            state,
            lifecycle,
            form_schema,
            route_rules,
            actor_bindings,
            sla_profile,
            lock_version,
        ) = row

        _check_policy_admin(cursor, actor.id, type_id=type_id)

        if state == "PUBLISHED":
            raise CommandError("RELEASE_IMMUTABLE", status=409)

        if lock_version != expected_version:
            raise CommandError(ERR_VERSION_CONFLICT, status=409)

        errors = validate_config_release_payload(
            lifecycle=lifecycle,
            form_schema=form_schema,
            route_rules=route_rules,
            actor_bindings=actor_bindings,
            sla_profile=sla_profile,
        )
        if type_code == "RESIGNATION" and not route_rules.get("executor"):
            errors.append("RESIGNATION:executor must be configured for offboarding checklist")
        if type_code in {"ACCESS_FACILITY","BUSINESS_TRIP","EQUIPMENT_BORROW", "EXPENSE_CLAIM", "IT_SUPPORT", "LEAVE_SPECIAL", "ROOM_BOOKING"} and isinstance(form_schema.get("properties"), dict) and set(form_schema["properties"]) <= {"title","reason"}:
            errors.append("form_schema:define business-specific fields for this request type before publishing")
        if not errors:
            errors.extend(role_grant_errors(cursor, type_id, route_rules, actor_bindings))
        if errors:
            raise CommandError("CONFIG_INVALID", status=422, fields=errors)

        canonical_obj = {
            "actor_bindings": actor_bindings,
            "form_schema": form_schema,
            "lifecycle": lifecycle,
            "route_rules": route_rules,
            "sla_profile": sla_profile,
            "type_id": type_id,
        }
        content_sha256 = canonical_sha256(canonical_obj)

        if val_hash and val_hash != content_sha256:
            raise CommandError("VALIDATION_STALE", status=409)

        cursor.execute(
            """
            UPDATE eas.config_release
            SET state = 'PUBLISHED',
                published_by = %s,
                published_at = statement_timestamp(),
                content_sha256 = %s,
                lock_version = lock_version + 1
            WHERE id = %s
            RETURNING lock_version, published_at
            """,
            [actor.id, content_sha256, norm_id],
        )
        new_lock_version, published_at = cursor.fetchone()

        cursor.execute(
            """
            UPDATE eas.request_type
            SET active_release_id = %s
            WHERE id = %s
            """,
            [norm_id, type_id],
        )

        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="CONFIG_RELEASE_PUBLISHED",
            target_type="config_release",
            target_id=norm_id,
            type_id=type_id,
            details={
                "release_id": norm_id,
                "version": version,
                "content_sha256": content_sha256,
            },
            reason=reason,
            correlation_id=correlation_id,
            occurred_at=published_at,
        )

        from api_core.maintenance import start_maintenance

        m_info = start_maintenance(
            actor_id=actor.id,
            release_id=norm_id,
            message="Hệ thống đang bảo trì để cập nhật quy định mới và huấn luyện AI, vui lòng quay lại sau.",
            admin_message=f"Hệ thống đang trong quá trình cập nhật quy định mới ({type_code} v{version}). Chỉ quản trị viên mới có thể truy cập web-admin.",
        )

        return (
            {
                "release": {
                    "id": norm_id,
                    "type_code": type_code,
                    "version": version,
                    "state": "PUBLISHED",
                    "content_sha256": content_sha256,
                    "lock_version": new_lock_version,
                },
                "maintenance": {
                    "active": True,
                    "status": "UPDATING",
                    "message": m_info["admin_message"],
                },
            },
            200,
            None,
        )

    return _execute_idempotent(
        actor_id=actor.id,
        scope=f"config:publish:{norm_id}",
        key=idempotency_key,
        command_body=body,
        operation=_op,
    )
