"""Audited identity administration. Global OPS_ADMIN/ALL only.

Delete means deactivate or revoke; referenced business records remain intact.
No password hashes are returned or written into audit payloads.
"""

from datetime import datetime, timezone
import re
from django.conf import settings
from uuid import UUID, uuid4

from django.contrib.auth.hashers import make_password
from django.db import connection, transaction

from api_core.audit import canonical_sha256
from api_core.authn.service import PasswordChangeError, validate_new_password
from api_core.workflow.service import (
    CommandError,
    _append_admin_audit,
    _execute_idempotent,
)

ROLES = {
    "REQUESTER",
    "APPROVER",
    "EXECUTOR",
    "ACCEPTOR",
    "POLICY_ADMIN",
    "OPS_ADMIN",
    "AUDITOR",
}
TABLES = {
    "departments": ("department", ("id", "code", "name", "parent_id", "is_active")),
    "users": (
        "app_user",
        (
            "id",
            "username",
            "display_name",
            "department_id",
            "manager_id",
            "is_active",
            "auth_version",
            "must_change_password",
        ),
    ),
    "memberships": (
        "role_membership",
        (
            "id",
            "user_id",
            "role",
            "scope_kind",
            "department_id",
            "type_scope",
            "type_id",
            "valid_from",
            "valid_to",
            "revoked_at",
        ),
    ),
    "request-types": (
        "request_type",
        ("id", "code", "lifecycle", "is_active", "active_release_id"),
    ),
}


def authorize(cursor, actor):
    cursor.execute(
        """SELECT EXISTS(SELECT 1 FROM eas.role_membership m
        JOIN eas.app_user u ON u.id=m.user_id
        WHERE m.user_id=%s AND u.is_active AND u.auth_version=%s
        AND m.role='OPS_ADMIN' AND m.scope_kind='GLOBAL' AND m.type_scope='ALL'
        AND m.revoked_at IS NULL AND m.valid_from<=statement_timestamp()
        AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp()))""",
        [actor.id, actor.auth_version],
    )
    if not cursor.fetchone()[0]:
        raise CommandError("FORBIDDEN", status=403)


def uid(value, field, nullable=False):
    if nullable and value in (None, ""):
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise CommandError("INVALID_" + field.upper(), status=422) from None


def text(value, field, max_length=150):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_length:
        raise CommandError("INVALID_" + field.upper(), status=422)
    return value.strip()


def boolean(value):
    if type(value) is not bool:
        raise CommandError("INVALID_BOOLEAN", status=422)
    return value


def timestamp(value, nullable=False):
    if nullable and not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise ValueError
        return t.isoformat()
    except (ValueError, TypeError, AttributeError):
        raise CommandError("INVALID_DATETIME", status=422) from None


def serialize(columns, row):
    value = {
        k: (
            v.isoformat()
            if isinstance(v, datetime)
            else str(v)
            if isinstance(v, UUID)
            else v
        )
        for k, v in zip(columns, row)
    }
    value["revision"] = canonical_sha256(value)
    return value


def _list_filters(kind, query):
    """Parameterize values; only fields from a fixed allowlist reach SQL."""
    q = str(query.get("q", "")).strip()
    if len(q) > 100:
        raise CommandError("INVALID_SEARCH", status=422)
    role = str(query.get("role", "")).strip()
    if role and role not in ROLES:
        raise CommandError("INVALID_ROLE", status=422)
    if role and kind not in {"users", "memberships"}:
        raise CommandError("INVALID_FILTER", status=422)
    active = query.get("active", "")
    if active not in ("", "true", "false") or (active and kind not in {"users", "departments", "request-types"}):
        raise CommandError("INVALID_FILTER", status=422)
    user_id = query.get("user_id", "")
    if user_id and kind != "memberships":
        raise CommandError("INVALID_FILTER", status=422)
    department_id = query.get("department_id", "")
    if department_id and kind not in {"users", "memberships"}:
        raise CommandError("INVALID_FILTER", status=422)
    state = query.get("state", "")
    if state and (kind != "memberships" or state not in {"ACTIVE", "REVOKED", "EXPIRED", "FUTURE"}):
        raise CommandError("INVALID_FILTER", status=422)
    clauses, params = [], []
    if state == "REVOKED":
        clauses.append("t.revoked_at IS NOT NULL")
    elif state == "ACTIVE":
        clauses.append("t.revoked_at IS NULL AND t.valid_from<=statement_timestamp() AND (t.valid_to IS NULL OR t.valid_to>statement_timestamp())")
    elif state == "EXPIRED":
        clauses.append("t.revoked_at IS NULL AND t.valid_to<=statement_timestamp()")
    elif state == "FUTURE":
        clauses.append("t.revoked_at IS NULL AND t.valid_from>statement_timestamp()")
    searchable = {
        "users": ("username", "display_name"),
        "departments": ("code", "name"),
        "request-types": ("code", "lifecycle"),
        "memberships": ("role", "user_id::text"),
    }
    if q:
        cols = searchable[kind]
        clauses.append("(" + " OR ".join(f"t.{col} ILIKE %s" for col in cols) + ")")
        params.extend([f"%{q}%"] * len(cols))
    if active:
        clauses.append("t.is_active=%s")
        params.append(active == "true")
    if user_id:
        clauses.append("t.user_id=%s")
        params.append(uid(user_id, "user_id"))
    if department_id:
        clauses.append("t.department_id=%s")
        params.append(uid(department_id, "department_id"))
    if role:
        if kind == "memberships":
            clauses.append("t.role=%s")
        else:
            clauses.append("""EXISTS (
                SELECT 1 FROM eas.role_membership rm WHERE rm.user_id=t.id
                AND rm.role=%s AND rm.revoked_at IS NULL
                AND rm.valid_from<=statement_timestamp()
                AND (rm.valid_to IS NULL OR rm.valid_to>statement_timestamp())
            )""")
        params.append(role)
    return " WHERE " + " AND ".join(clauses) if clauses else "", params


def list_records(actor, kind, query):
    table, columns = TABLES[kind]
    try:
        limit = int(query.get("limit", 50))
        offset = int(query.get("offset", 0))
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise ValueError
    except (ValueError, TypeError):
        raise CommandError("INVALID_PAGINATION", status=400) from None
    where, params = _list_filters(kind, query)
    fields = ",".join("t." + field for field in columns)
    order = {"users": "t.username,t.id", "departments": "t.code,t.id", "memberships": "t.role,t.id", "request-types": "t.code,t.id"}[kind]
    with transaction.atomic(), connection.cursor() as c:
        c.execute("SELECT eas.lock_security(false)")
        authorize(c, actor)
        c.execute(f"SELECT COUNT(*) FROM eas.{table} t{where}", params)
        total = int(c.fetchone()[0])
        c.execute(
            f"SELECT {fields} FROM eas.{table} t{where} ORDER BY {order} LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = c.fetchall()
    return {
        "items": [serialize(columns, r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + limit if offset + limit < total else None,
    }


def read_record(actor, kind, record_id):
    table, columns = TABLES[kind]
    record_id = uid(record_id, "id")
    with transaction.atomic(), connection.cursor() as c:
        c.execute("SELECT eas.lock_security(false)")
        authorize(c, actor)
        c.execute(f"SELECT {','.join(columns)} FROM eas.{table} WHERE id=%s", [record_id])
        row = c.fetchone()
        if not row:
            raise CommandError("NOT_FOUND", status=404)
        item = serialize(columns, row)
        if kind == "users":
            member_columns = TABLES["memberships"][1]
            c.execute(
                f"SELECT {','.join(member_columns)} FROM eas.role_membership WHERE user_id=%s ORDER BY role,id",
                [record_id],
            )
            item["memberships"] = [serialize(member_columns, r) for r in c.fetchall()]
    return {"item": item}


def validate(kind, body, old=None):
    allowed = {"reason", "expected_revision"} | {
        "users": {
            "username",
            "display_name",
            "department_id",
            "manager_id",
            "is_active",
            "password",
        },
        "departments": {"code", "name", "parent_id", "is_active"},
        "memberships": {
            "user_id",
            "role",
            "scope_kind",
            "department_id",
            "type_scope",
            "type_id",
            "valid_from",
            "valid_to",
        },
        "request-types": ({"is_active", "code", "lifecycle"} if old is None else {"is_active"}),
    }[kind]
    if set(body) - allowed:
        raise CommandError("UNKNOWN_FIELD", status=422)
    v = dict(old or {})
    v.update(
        {k: x for k, x in body.items() if k not in {"reason", "expected_revision"}}
    )
    if kind == "users":
        v = {
            **v,
            "username": text(v.get("username"), "username").lower(),
            "display_name": text(v.get("display_name"), "display_name"),
            "department_id": uid(v.get("department_id"), "department_id"),
            "manager_id": uid(v.get("manager_id"), "manager_id", True),
            "is_active": boolean(v.get("is_active", True)),
        }
        if not old or body.get("password"):
            try:
                v["password_hash"] = make_password(
                    validate_new_password(body.get("password"), v["username"]),
                    hasher="argon2",
                )
            except PasswordChangeError:
                raise CommandError("PASSWORD_POLICY_VIOLATION", status=422) from None
        v.pop("password", None)
    elif kind == "departments":
        v = {
            **v,
            "code": text(v.get("code"), "code", 50),
            "name": text(v.get("name"), "name"),
            "parent_id": uid(v.get("parent_id"), "parent_id", True),
            "is_active": boolean(v.get("is_active", True)),
        }
    elif kind == "memberships":
        v["user_id"] = uid(v.get("user_id"), "user_id")
        if old and old["user_id"] != v["user_id"]:
            raise CommandError("MEMBERSHIP_OWNER_IMMUTABLE", status=422)
        if (
            v.get("role") not in ROLES
            or v.get("scope_kind") not in {"GLOBAL", "DEPARTMENT"}
            or v.get("type_scope") not in {"ALL", "ONE"}
        ):
            raise CommandError("INVALID_ROLE_SCOPE", status=422)
        v["department_id"] = uid(v.get("department_id"), "department_id", True)
        v["type_id"] = uid(v.get("type_id"), "type_id", True)
        if (v["scope_kind"] == "DEPARTMENT") != (v["department_id"] is not None) or (
            v["type_scope"] == "ONE"
        ) != (v["type_id"] is not None):
            raise CommandError("INVALID_ROLE_SCOPE", status=422)
        v["valid_from"] = timestamp(
            v.get("valid_from") or datetime.now(timezone.utc).isoformat()
        )
        v["valid_to"] = timestamp(v.get("valid_to"), True)
        if v["valid_to"] and datetime.fromisoformat(
            v["valid_to"]
        ) <= datetime.fromisoformat(v["valid_from"]):
            raise CommandError("INVALID_VALIDITY_WINDOW", status=422)
    elif kind == "request-types":
        v["is_active"] = boolean(v.get("is_active", True))
        if old is None:
            code = v.get("code")
            lifecycle = v.get("lifecycle")
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,29}", code):
                raise CommandError("INVALID_TYPE_CODE", status=422)
            if lifecycle not in {"A", "B", "C"}:
                raise CommandError("INVALID_LIFECYCLE", status=422)
            v["code"] = code
            v["lifecycle"] = lifecycle
    else:
        raise CommandError("INVALID_KIND", status=422)
    return v


def active_reference(c, table, id):
    if id is None:
        return
    c.execute(f"SELECT 1 FROM eas.{table} WHERE id=%s AND is_active", [id])
    if not c.fetchone():
        raise CommandError("REFERENCE_INACTIVE_OR_MISSING", status=422)


def check_cycle(c, table, parent_field, id, parent):
    if not parent:
        return
    c.execute(
        f"""WITH RECURSIVE chain AS (
       SELECT id,{parent_field} FROM eas.{table} WHERE id=%s
       UNION SELECT t.id,t.{parent_field} FROM eas.{table} t JOIN chain p ON t.id=p.{parent_field}
    ) SELECT 1 FROM chain WHERE id=%s LIMIT 1""",
        [parent, id],
    )
    if c.fetchone():
        raise CommandError("HIERARCHY_CYCLE", status=422)


def mutate(actor, kind, record_id, body, method, key, correlation_id):
    table, columns = TABLES[kind]
    if method == "POST" and kind == "request-types" and not settings.EAS_ALLOW_REPORT_CATALOG_EXPANSION:
        raise CommandError("CATALOG_EXPANSION_DISABLED", status=403)
    reason = text(body.get("reason"), "reason", 2000)
    if len(reason) < 10:
        raise CommandError("REASON_INVALID", status=422)
    id = uid(record_id, "id") if record_id else str(uuid4())

    def operation(c):
        old = None
        if method != "POST":
            c.execute(
                f"SELECT {','.join(columns)} FROM eas.{table} WHERE id=%s FOR UPDATE",
                [id],
            )
            row = c.fetchone()
            if not row:
                raise CommandError("NOT_FOUND", status=404)
            old = serialize(columns, row)
            if body.get("expected_revision") != old["revision"]:
                raise CommandError("VERSION_CONFLICT", status=409)
        if method == "DELETE":
            if set(body) - {"reason", "expected_revision"}:
                raise CommandError("UNKNOWN_FIELD", status=422)
            v = dict(old)
            if kind == "memberships":
                v["revoked_at"] = datetime.now(timezone.utc).isoformat()
            else:
                v["is_active"] = False
        else:
            v = validate(kind, body, old)
        if kind == "users":
            if id == actor.id:
                raise CommandError("SELF_ADMIN_CHANGE_FORBIDDEN", status=403)
            active_reference(c, "department", v["department_id"])
            active_reference(c, "app_user", v.get("manager_id"))
            check_cycle(c, "app_user", "manager_id", id, v.get("manager_id"))
        elif kind == "departments":
            active_reference(c, "department", v.get("parent_id"))
            check_cycle(c, "department", "parent_id", id, v.get("parent_id"))
            if not v["is_active"]:
                c.execute(
                    "SELECT 1 FROM eas.app_user WHERE department_id=%s AND is_active UNION ALL SELECT 1 FROM eas.department WHERE parent_id=%s AND is_active LIMIT 1",
                    [id, id],
                )
                if c.fetchone():
                    raise CommandError("DEPARTMENT_IN_USE", status=409)
        elif kind == "memberships":
            if v["user_id"] == actor.id:
                raise CommandError("SELF_ADMIN_CHANGE_FORBIDDEN", status=403)
            if old and old.get("revoked_at"):
                raise CommandError("MEMBERSHIP_REVOKED", status=409)
            if method != "DELETE":
                active_reference(c, "app_user", v["user_id"])
                active_reference(c, "department", v.get("department_id"))
                active_reference(c, "request_type", v.get("type_id"))
        fields = {
            "users": [
                "username",
                "display_name",
                "department_id",
                "manager_id",
                "is_active",
            ],
            "departments": ["code", "name", "parent_id", "is_active"],
            "memberships": [
                "user_id",
                "role",
                "scope_kind",
                "department_id",
                "type_scope",
                "type_id",
                "valid_from",
                "valid_to",
            ],
            "request-types": (["code", "lifecycle", "is_active"] if method == "POST" else ["is_active"]),
        }[kind].copy()
        if kind == "users":
            v["auth_version"] = (old or {}).get("auth_version", 0) + 1
            fields.append("auth_version")
            if "password_hash" in v:
                fields += ["password_hash", "must_change_password"]
                v["must_change_password"] = True
        if kind == "memberships" and method == "DELETE":
            fields = ["revoked_at"]
        if method == "POST":
            c.execute(
                f"INSERT INTO eas.{table} (id,{','.join(fields)}) VALUES ({','.join(['%s'] * (len(fields) + 1))})",
                [id] + [v[f] for f in fields],
            )
        else:
            c.execute(
                f"UPDATE eas.{table} SET {','.join(f + '=%s' for f in fields)} WHERE id=%s",
                [v[f] for f in fields] + [id],
            )
        if kind == "memberships":
            c.execute(
                "UPDATE eas.app_user SET auth_version=auth_version+1 WHERE id=%s",
                [v["user_id"]],
            )
        c.execute(
            "UPDATE eas.security_epoch SET version=version+1,updated_at=statement_timestamp() WHERE id=1"
        )
        c.execute(f"SELECT {','.join(columns)} FROM eas.{table} WHERE id=%s", [id])
        after = serialize(columns, c.fetchone())
        _append_admin_audit(
            c,
            actor_id=actor.id,
            action="ADMIN_" + method,
            target_type=table,
            target_id=id,
            reason=reason,
            details={
                "before": old,
                "after": after,
                "password_reset": "password_hash" in v,
            },
            correlation_id=correlation_id,
        )
        return {"item": after}, 201 if method == "POST" else 200, None

    # Acquire exclusive lock BEFORE the shared-lock idempotency helper to avoid lock upgrade races.
    with transaction.atomic(), connection.cursor() as c:
        c.execute("SELECT eas.lock_security(true)")
        authorize(c, actor)
        return _execute_idempotent(
            actor_id=actor.id,
            scope=f"admin:{kind}:{method}:{record_id or 'new'}",
            key=key,
            command_body=body,
            operation=operation,
        )
