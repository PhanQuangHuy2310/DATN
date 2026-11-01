"""
Router: Policy — Nạp quy định nghiệp vụ dạng bộ luật cho AI

POST /ai/policy/rules  — thay toàn bộ bộ luật đang áp dụng (atomic)
GET  /ai/policy/rules  — bộ luật hiện hành

Bộ luật được đọc lại theo mtime ở mỗi lần đánh giá auto-approve, nên có hiệu
lực ngay ở request kế tiếp mà không cần train lại model hay restart service.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

router = APIRouter()

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
POLICY_FILE = os.path.join(DATA_DIR, "active_enterprise_policy.json")

_cache: dict = {"mtime": None, "path": None, "policy": None}


class PolicyRule(BaseModel):
    id: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=500)
    request_type: str | None = Field(None, max_length=60)
    amount_gt: float | None = Field(None, ge=0)
    days_gt: int | None = Field(None, ge=0)
    min_risk: int | None = Field(None, ge=1, le=5)
    auto_approve: bool | None = None

    @model_validator(mode="after")
    def has_effect(self):
        if self.min_risk is None and self.auto_approve is None:
            raise ValueError("rule needs min_risk or auto_approve")
        return self


class PolicyDocument(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    rules: list[PolicyRule] = Field(default_factory=list, max_length=200)


class PolicyState(PolicyDocument):
    loaded_at: str | None = None


_PULL_RETRY_SECONDS = 60
_last_pull = {"at": 0.0}


def pull_active_policy(path: str | None = None) -> PolicyState | None:
    """Fill an empty cache from the API (eas.ai_policy_version is the source)."""
    import time

    if time.monotonic() - _last_pull["at"] < _PULL_RETRY_SECONDS:
        return None
    _last_pull["at"] = time.monotonic()
    try:
        import httpx

        try:
            from config import get_settings
        except (ImportError, AttributeError):
            from ai_service.config import get_settings
        settings = get_settings()
        response = httpx.get(
            f"{settings.eas_api_internal_url.rstrip('/')}/api/v1/internal/ai-policy/active",
            headers={"X-Internal-Secret": settings.internal_api_secret},
            timeout=3.0,
        )
        if response.status_code != 200:
            return None
        return save_policy(PolicyDocument.model_validate(response.json()), path)
    except Exception:  # noqa: BLE001 - no policy cache keeps the model defaults
        return None


def load_policy(path: str | None = None) -> PolicyState | None:
    path = path or POLICY_FILE
    try:
        mtime = os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return pull_active_policy(path)
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return _cache["policy"]
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    try:
        policy = PolicyState.model_validate(raw)
    except ValueError:
        policy = None  # legacy free-text policy files carry no rules
    _cache.update(mtime=mtime, path=path, policy=policy)
    return policy


def save_policy(document: PolicyDocument, path: str | None = None) -> PolicyState:
    path = path or POLICY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    state = PolicyState(
        **document.model_dump(), loaded_at=datetime.now(timezone.utc).isoformat()
    )
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state.model_dump(), handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return state


def apply_policy(
    *, request_type: str, amount: float, days: int, risk: int, path: str | None = None
) -> tuple[int, bool, list[str], str | None]:
    """Return (effective risk, manual review forced, matched rule ids, version)."""
    policy = load_policy(path)
    if policy is None:
        return risk, False, [], None
    forced_manual = False
    matched = []
    for rule in policy.rules:
        if rule.request_type and rule.request_type != request_type:
            continue
        if rule.amount_gt is not None and not amount > rule.amount_gt:
            continue
        if rule.days_gt is not None and not days > rule.days_gt:
            continue
        matched.append(rule.id)
        if rule.min_risk is not None:
            risk = max(risk, rule.min_risk)
        if rule.auto_approve is False:
            forced_manual = True
    return risk, forced_manual, matched, policy.version


@router.post("/rules", response_model=PolicyState, summary="Nạp bộ luật quy định")
async def publish_rules(body: PolicyDocument):
    return save_policy(body)


@router.get("/rules", response_model=PolicyState | None, summary="Bộ luật hiện hành")
async def current_rules():
    return load_policy()
