"""No-dependency source regression checks for UC17 and API inventory.
Run from repository root: python verify_uc17_static.py
Does not connect to DB or change files.
"""
import ast
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parent
catalog_path = ROOT / "api_core/administration/catalog.py"
spec = spec_from_file_location("eas_uc17_catalog", catalog_path)
catalog = module_from_spec(spec)
spec.loader.exec_module(catalog)

assert len(catalog.ROLE_MATRIX) == 7
roles = {x["role"] for x in catalog.ROLE_MATRIX}
assert roles == {"REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR", "POLICY_ADMIN", "OPS_ADMIN", "AUDITOR"}
assert len(catalog.API_ENDPOINTS) >= 35
assert len({(x["method"], x["path"]) for x in catalog.API_ENDPOINTS}) == len(catalog.API_ENDPOINTS)
assert all(x["path"].startswith("/api/v1/") for x in catalog.API_ENDPOINTS)
assert catalog.api_catalog()["mutable"] is False
assert all("password_hash" not in str(x) for x in catalog.API_ENDPOINTS)

service_path = ROOT / "api_core/administration/service.py"
parsed = ast.parse(service_path.read_text(encoding="utf-8"))
filters = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == "_list_filters")

class CommandError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status

from uuid import UUID

def uid(x, field):
    return str(UUID(str(x)))

scope = {"CommandError": CommandError, "ROLES": roles, "uid": uid}
exec(compile(ast.fix_missing_locations(ast.Module(body=[filters], type_ignores=[])), str(service_path), "exec"), scope)
filter_fn = scope["_list_filters"]
payload = "' OR true --"
clause, params = filter_fn("users", {"q": payload, "role": "APPROVER", "active": "true"})
assert payload not in clause and f"%{payload}%" in params
assert "rm.role=%s" in clause and params[-1] == "APPROVER"
for kind, query in [
    ("users", {"role": "SUPERUSER"}),
    ("memberships", {"active": "false"}),
    ("users", {"q": "x" * 101}),
    ("users", {"state": "REVOKED"}),
]:
    try:
        filter_fn(kind, query)
    except CommandError:
        pass
    else:
        raise AssertionError((kind, query))
assert "t.revoked_at IS NOT NULL" in filter_fn("memberships", {"state": "REVOKED"})[0]
assert "t.valid_from>statement_timestamp()" in filter_fn("memberships", {"state": "FUTURE"})[0]

urls = (ROOT / "api_core/administration/urls.py").read_text(encoding="utf-8")
assert urls.index('path("api-catalog"') < urls.index('path("<str:kind>"')
assert urls.index('path("access-matrix"') < urls.index('path("<str:kind>"')
views = (ROOT / "api_core/administration/views.py").read_text(encoding="utf-8")
assert "authorize(cursor, request.actor)" in views
assert 'read_record(request.actor, kind' in views

print("PASS: 7 roles, API catalog contracts, global admin authorization, safe filters, admin URL ordering")
