import contextlib
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import _append_admin_audit


def _detect_cycle(graph: dict[str, str | None]) -> list[str] | None:
    # graph maps child -> parent
    for start_node in graph:
        visited = set()
        curr: str | None = start_node
        path = []
        while curr:
            if curr in visited:
                path.append(curr)
                return path
            visited.add(curr)
            path.append(curr)
            curr = graph.get(curr)
    return None


def _read_manifest(manifest_path: Path, stderr) -> tuple[dict, str]:
    if not manifest_path.exists():
        stderr.write(f"ERROR: Manifest file not found: {manifest_path}")
        sys.exit(2)
    try:
        raw_bytes = manifest_path.read_bytes()
        data = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        stderr.write(f"ERROR: Failed to read JSON manifest: {exc}")
        sys.exit(2)
    return data, hashlib.sha256(raw_bytes).hexdigest()


def _validate_departments_manifest(departments: list[dict]) -> list[str]:
    errors: list[str] = []
    dept_codes = set()
    dept_ids = set()
    dept_parents: dict[str, str | None] = {}
    dept_parent_codes: dict[str, str | None] = {}
    for idx, d in enumerate(departments):
        d_id = d.get("id")
        code = d.get("code")
        if not code or not str(code).strip():
            errors.append(f"Department [{idx}]: code must be non-empty.")
        elif code in dept_codes:
            errors.append(f"Department [{idx}]: duplicate code '{code}'.")
        else:
            dept_codes.add(code)
            parent_code = d.get("parent_code")
            dept_parent_codes[code] = str(parent_code).strip() if parent_code else None

        if d_id:
            try:
                norm_id = str(UUID(d_id))
                dept_ids.add(norm_id)
                parent_id = d.get("parent_id")
                dept_parents[norm_id] = str(UUID(parent_id)) if parent_id else None
            except ValueError:
                errors.append(f"Department [{idx}]: invalid UUID.")

    dept_cycle = _detect_cycle(dept_parents)
    if dept_cycle:
        errors.append(
            f"Department hierarchy contains a cycle: {' -> '.join(dept_cycle)}"
        )
    dept_code_cycle = _detect_cycle(dept_parent_codes)
    if dept_code_cycle:
        errors.append(
            f"Department hierarchy contains a cycle: {' -> '.join(dept_code_cycle)}"
        )
    return errors


def _validate_users_manifest(users: list[dict]) -> list[str]:
    errors: list[str] = []
    usernames = set()
    user_ids = set()
    user_managers: dict[str, str | None] = {}
    for idx, u in enumerate(users):
        u_id = u.get("id")
        username = u.get("username")
        if not username or not str(username).strip():
            errors.append(f"User [{idx}]: username must be non-empty.")
        elif username in usernames:
            errors.append(f"User [{idx}]: duplicate username '{username}'.")
        else:
            usernames.add(username)

        if u_id:
            try:
                norm_uid = str(UUID(u_id))
                user_ids.add(norm_uid)
                mgr_id = u.get("manager_id")
                user_managers[norm_uid] = str(UUID(mgr_id)) if mgr_id else None
            except ValueError:
                errors.append(f"User [{idx}]: invalid UUID.")

    user_cycle = _detect_cycle(user_managers)
    if user_cycle:
        errors.append(
            f"User management hierarchy contains a cycle: {' -> '.join(user_cycle)}"
        )
    return errors


def _validate_roles_manifest(roles: list[dict]) -> list[str]:
    errors: list[str] = []
    for idx, r in enumerate(roles):
        u_id = r.get("user_id")
        if not u_id:
            errors.append(f"Role [{idx}]: missing user_id.")
        scope_kind = r.get("scope_kind", "GLOBAL")
        dept_id = r.get("department_id")
        if scope_kind == "GLOBAL" and dept_id is not None:
            errors.append(
                f"Role [{idx}]: GLOBAL scope must have department_id as null."
            )
        elif scope_kind == "DEPARTMENT" and dept_id is None:
            errors.append(
                f"Role [{idx}]: DEPARTMENT scope requires non-null department_id."
            )

        type_scope = r.get("type_scope", "ALL")
        type_id = r.get("type_id")
        if type_scope == "ALL" and type_id is not None:
            errors.append(f"Role [{idx}]: ALL type_scope must have type_id as null.")
        elif type_scope == "ONE" and type_id is None:
            errors.append(f"Role [{idx}]: ONE scope requires non-null type_id.")
    return errors


def _apply_identity_changes(
    cursor,
    *,
    departments: list[dict],
    users: list[dict],
    roles: list[dict],
    operator: str,
    approval: str,
    manifest_sha256: str,
    correlation_id: str,
) -> list[str]:
    cursor.execute("SELECT eas.lock_security(true)")

    cursor.execute(
        "SELECT id::text FROM eas.app_user WHERE username = %s OR id::text = %s",
        [operator, operator],
    )
    op_row = cursor.fetchone()
    operator_id = op_row[0] if op_row else None

    for d in departments:
        cursor.execute(
            """
            INSERT INTO eas.department(id, code, name, parent_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET code = EXCLUDED.code, name = EXCLUDED.name, parent_id = EXCLUDED.parent_id
            """,
            [d["id"], d["code"], d["name"], d.get("parent_id")],
        )

    affected_user_ids = []
    for u in users:
        uid = u["id"]
        affected_user_ids.append(uid)
        is_active = u.get("is_active", True)
        cursor.execute(
            """
            INSERT INTO eas.app_user(id, username, display_name, department_id, manager_id, is_active, password_hash, auth_version)
            VALUES (%s, %s, %s, %s, %s, %s, '!TEMP_IMPORT_PASSWORD', 1)
            ON CONFLICT (id) DO UPDATE
            SET username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                department_id = EXCLUDED.department_id,
                manager_id = EXCLUDED.manager_id,
                is_active = EXCLUDED.is_active,
                auth_version = eas.app_user.auth_version + 1
            """,
            [
                uid,
                u["username"],
                u["display_name"],
                u.get("department_id"),
                u.get("manager_id"),
                is_active,
            ],
        )

    for r in roles:
        role_id = r.get("id") or str(uuid4())
        cursor.execute(
            """
            INSERT INTO eas.role_membership(id, user_id, role, department_id, type_id, scope_kind, type_scope)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET role = EXCLUDED.role,
                department_id = EXCLUDED.department_id,
                type_id = EXCLUDED.type_id,
                scope_kind = EXCLUDED.scope_kind,
                type_scope = EXCLUDED.type_scope,
                revoked_at = NULL
            """,
            [
                role_id,
                r["user_id"],
                r["role"],
                r.get("department_id"),
                r.get("type_id"),
                r.get("scope_kind", "GLOBAL"),
                r.get("type_scope", "ALL"),
            ],
        )

    cursor.execute(
        "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
    )

    _append_admin_audit(
        cursor,
        actor_id=operator_id,
        action="IDENTITY_IMPORTED",
        target_type="manifest",
        target_id=manifest_sha256,
        reason=approval,
        details={
            "manifest_sha256": manifest_sha256,
            "departments_count": len(departments),
            "users_count": len(users),
            "roles_count": len(roles),
        },
        correlation_id=correlation_id,
    )
    return affected_user_ids


class Command(BaseCommand):
    help = "Import or update organizational identity manifest (departments, users, roles) with audit."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest", required=True, help="Path to manifest JSON file."
        )
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "--dry-run", action="store_true", help="Validate without applying changes."
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes in a database transaction.",
        )
        parser.add_argument(
            "--operator",
            required=False,
            help="Operator username or UUID (required for --apply).",
        )
        parser.add_argument(
            "--approval",
            required=False,
            help="Change approval reference (required for --apply).",
        )

    def handle(self, *args, **options):
        manifest_path = Path(options["manifest"])
        data, manifest_sha256 = _read_manifest(manifest_path, self.stderr)

        departments = data.get("departments", [])
        users = data.get("users", [])
        roles = data.get("roles", [])

        errors = (
            _validate_departments_manifest(departments)
            + _validate_users_manifest(users)
            + _validate_roles_manifest(roles)
        )

        if errors:
            self.stderr.write("Validation failed with the following errors:")
            for err in errors:
                self.stderr.write(f"  - {err}")
            sys.exit(2)

        if options["dry_run"]:
            self.stdout.write(f"Manifest SHA256: {manifest_sha256}")
            self.stdout.write(
                f"Valid manifest: {len(departments)} departments, {len(users)} users, {len(roles)} roles."
            )
            self.stdout.write("Dry run completed successfully. No changes applied.")
            sys.exit(0)

        operator = options.get("operator")
        approval = options.get("approval")
        if not operator or not str(operator).strip():
            self.stderr.write(
                "ERROR: --operator is required when --apply is specified."
            )
            sys.exit(2)
        if not approval or not str(approval).strip():
            self.stderr.write(
                "ERROR: --approval is required when --apply is specified."
            )
            sys.exit(2)

        correlation_id = str(uuid4())

        with transaction.atomic(), connection.cursor() as cursor:
            affected_user_ids = _apply_identity_changes(
                cursor,
                departments=departments,
                users=users,
                roles=roles,
                operator=operator,
                approval=approval,
                manifest_sha256=manifest_sha256,
                correlation_id=correlation_id,
            )

        for uid in affected_user_ids:
            with contextlib.suppress(Exception):
                cache.delete(f"eas:session:{uid}")

        self.stdout.write(
            f"Identity manifest successfully applied. SHA256: {manifest_sha256}"
        )
        sys.exit(0)
