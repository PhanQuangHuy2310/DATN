from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import connection, transaction


class QueryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceSpec:
    relation: str
    columns: tuple[str, ...]
    search_columns: tuple[str, ...]


RESOURCES = {
    "departments": ResourceSpec(
        "mock_hr.department",
        ("id", "code", "name", "cost_center", "status", "updated_at"),
        ("code", "name", "cost_center"),
    ),
    "employees": ResourceSpec(
        "mock_hr.employee_directory",
        (
            "id",
            "employee_code",
            "display_name",
            "work_email",
            "department_id",
            "manager_id",
            "job_title",
            "employment_status",
            "updated_at",
        ),
        ("employee_code", "display_name", "work_email", "job_title"),
    ),
    "leave-balances": ResourceSpec(
        "mock_hr.leave_balance",
        (
            "id",
            "employee_id",
            "leave_type",
            "year",
            "entitled_days",
            "used_days",
            "updated_at",
        ),
        ("leave_type",),
    ),
    "assets": ResourceSpec(
        "mock_assets.asset_catalog",
        (
            "id",
            "asset_code",
            "name",
            "category_code",
            "serial_number",
            "site_code",
            "condition",
            "availability_status",
            "updated_at",
        ),
        ("asset_code", "name", "category_code", "serial_number"),
    ),
    "asset-loans": ResourceSpec(
        "mock_assets.asset_loan",
        (
            "id",
            "asset_id",
            "borrower_employee_id",
            "starts_at",
            "due_at",
            "returned_at",
            "status",
            "updated_at",
        ),
        ("status",),
    ),
    "facilities": ResourceSpec(
        "mock_facilities.resource_catalog",
        (
            "id",
            "resource_code",
            "name",
            "resource_type",
            "site_code",
            "capacity",
            "availability_status",
            "updated_at",
        ),
        ("resource_code", "name", "resource_type", "site_code"),
    ),
    "customers": ResourceSpec(
        "mock_crm.customer_directory",
        (
            "id",
            "customer_code",
            "legal_name",
            "segment",
            "account_status",
            "account_owner_employee_id",
            "updated_at",
        ),
        ("customer_code", "legal_name", "segment"),
    ),
    "contracts": ResourceSpec(
        "mock_crm.contract",
        (
            "id",
            "contract_code",
            "customer_id",
            "starts_on",
            "ends_on",
            "currency",
            "value_minor",
            "status",
            "updated_at",
        ),
        ("contract_code", "status"),
    ),
    "suppliers": ResourceSpec(
        "mock_procurement.supplier_directory",
        (
            "id",
            "supplier_code",
            "legal_name",
            "category",
            "risk_rating",
            "status",
            "updated_at",
        ),
        ("supplier_code", "legal_name", "category"),
    ),
    "catalog-items": ResourceSpec(
        "mock_procurement.catalog_item",
        (
            "id",
            "sku",
            "name",
            "category",
            "supplier_id",
            "currency",
            "unit_price_minor",
            "status",
            "updated_at",
        ),
        ("sku", "name", "category"),
    ),
    "applications": ResourceSpec(
        "mock_it.application_catalog",
        (
            "id",
            "app_code",
            "name",
            "data_classification",
            "owner_employee_id",
            "status",
            "updated_at",
        ),
        ("app_code", "name", "data_classification"),
    ),
    "access-roles": ResourceSpec(
        "mock_it.access_role",
        (
            "id",
            "application_id",
            "role_code",
            "name",
            "risk_level",
            "requires_sod_review",
            "status",
            "updated_at",
        ),
        ("role_code", "name", "risk_level"),
    ),
    "it-services": ResourceSpec(
        "mock_it.service_catalog",
        (
            "id",
            "service_code",
            "name",
            "category",
            "default_priority",
            "target_hours",
            "status",
            "updated_at",
        ),
        ("service_code", "name", "category"),
    ),
    "budgets": ResourceSpec(
        "mock_finance.cost_center_budget",
        (
            "id",
            "cost_center",
            "fiscal_year",
            "currency",
            "approved_minor",
            "committed_minor",
            "spent_minor",
            "updated_at",
        ),
        ("cost_center", "currency"),
    ),
    "expense-categories": ResourceSpec(
        "mock_finance.expense_category",
        (
            "id",
            "category_code",
            "name",
            "receipt_required_above_minor",
            "daily_limit_minor",
            "currency",
            "status",
            "updated_at",
        ),
        ("category_code", "name", "currency"),
    ),
    "travel-policies": ResourceSpec(
        "mock_travel.travel_policy",
        (
            "id",
            "employee_grade",
            "travel_mode",
            "cabin_or_class",
            "max_amount_minor",
            "currency",
            "requires_quote_count",
            "status",
            "updated_at",
        ),
        ("employee_grade", "travel_mode", "cabin_or_class"),
    ),
    "travel-options": ResourceSpec(
        "mock_travel.travel_option",
        (
            "id",
            "option_code",
            "travel_mode",
            "origin",
            "destination",
            "departs_at",
            "arrives_at",
            "supplier_id",
            "currency",
            "price_minor",
            "refundable",
            "availability_status",
            "updated_at",
        ),
        ("option_code", "travel_mode", "origin", "destination"),
    ),
}

ALL_READER_ROLES = frozenset(
    {
        "REQUESTER",
        "APPROVER",
        "EXECUTOR",
        "ACCEPTOR",
        "POLICY_ADMIN",
        "OPS_ADMIN",
        "AUDITOR",
    }
)
RESOURCE_ROLES = {
    "leave-balances": frozenset({"POLICY_ADMIN", "OPS_ADMIN", "AUDITOR"}),
    "asset-loans": frozenset({"EXECUTOR", "OPS_ADMIN", "AUDITOR"}),
    "customers": frozenset({"APPROVER", "EXECUTOR", "OPS_ADMIN", "AUDITOR"}),
    "contracts": frozenset({"APPROVER", "OPS_ADMIN", "AUDITOR"}),
    "budgets": frozenset({"APPROVER", "POLICY_ADMIN", "OPS_ADMIN", "AUDITOR"}),
}


def _positive_limit(raw: str | None) -> int:
    if raw is None:
        return 25
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise QueryValidationError("INVALID_LIMIT") from None
    if not 1 <= value <= 100:
        raise QueryValidationError("INVALID_LIMIT")
    return value


def _cursor(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        raise QueryValidationError("INVALID_CURSOR") from None


def _literal_like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_resource(resource: str, params, *, roles: frozenset[str]) -> dict:
    spec = RESOURCES.get(resource)
    if spec is None:
        raise QueryValidationError("RESOURCE_NOT_FOUND")
    allowed_roles = RESOURCE_ROLES.get(resource, ALL_READER_ROLES)
    if not roles.intersection(allowed_roles):
        raise QueryValidationError("RESOURCE_FORBIDDEN")
    if set(params.keys()) - {"limit", "cursor", "q"}:
        raise QueryValidationError("UNKNOWN_QUERY_PARAMETER")
    limit = _positive_limit(params.get("limit"))
    cursor = _cursor(params.get("cursor"))
    query = (params.get("q") or "").strip()
    if len(query) > 100:
        raise QueryValidationError("INVALID_QUERY")

    predicates: list[str] = []
    values: list[object] = []
    if cursor:
        predicates.append("id > %s")
        values.append(cursor)
    if query:
        predicates.append(
            "("
            + " OR ".join(
                f"{column} ILIKE %s ESCAPE '\\'" for column in spec.search_columns
            )
            + ")"
        )
        values.extend([_literal_like_pattern(query)] * len(spec.search_columns))
    where = f" WHERE {' AND '.join(predicates)}" if predicates else ""
    columns = ", ".join(spec.columns)
    sql = f"SELECT {columns} FROM {spec.relation}{where} ORDER BY id LIMIT %s"
    values.append(limit + 1)
    with transaction.atomic(), connection.cursor() as db_cursor:
        db_cursor.execute("SET LOCAL statement_timeout = '2s'")
        db_cursor.execute(sql, values)
        rows = db_cursor.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [dict(zip(spec.columns, row, strict=True)) for row in rows]
    return {
        "items": items,
        "page": {
            "limit": limit,
            "has_more": has_more,
            "next_cursor": str(items[-1]["id"]) if has_more and items else None,
        },
    }
