"""AI regulation learning as a leased job (migration 12).

A change to the company regulations (or to the manual AI rule set) queues one
job in ``eas.ai_learning_job``. While a job is QUEUED or RUNNING the employee
portal is locked. A runner claims the job with a lease, so a process that dies
mid-way (runserver reload, crashed worker) only delays the job: the lease
expires and the next runner takes over. The job:

1. SNAPSHOT  reads the active regulations,
2. LEARN     compiles them into AI policy rules (deterministic, no LLM cost),
3. APPLY     pushes the rules to ai_service and verifies the engine uses them,
4. COMMIT    stores the effective policy, writes the changelog and the user
             announcement (what changed + how to work with the new process),
             and only then releases the lock.

After ``max_attempts`` failures the job is FAILED: the previous policy stays in
force, the lock is released and administrators get an announcement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

LOCK_CACHE_KEY = "eas:ai-learning:open-job"
LOCK_CACHE_SECONDS = 3
LEASE_SECONDS = 45
RETRY_BACKOFF_SECONDS = (15, 45, 120)
ADMIN_ROLES = frozenset({"OPS_ADMIN", "POLICY_ADMIN", "AUDITOR"})

STEP_LABELS = {
    1: "Tiếp nhận & chụp bộ quy định hiện hành",
    2: "AI phân tích văn bản và trích bộ luật duyệt",
    3: "Áp dụng bộ luật vào AI và kiểm thử",
    4: "Hoàn tất, gửi thông báo và mở khoá",
}
STEP_STATUS = {1: "SYNCING", 2: "LEARNING", 3: "APPLYING", 4: "COMPLETED"}


class TransientLearningError(RuntimeError):
    """Retryable failure (AI service unreachable, timeout)."""


# ---------------------------------------------------------------------------
# 1. Regulation compiler: Vietnamese text -> policy rules (pure functions)
# ---------------------------------------------------------------------------

_MONEY = re.compile(
    r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>tỷ|ty|triệu|trieu|nghìn|nghin|ngàn|vnđ|vnd|đồng|dong|đ)\b",
    re.IGNORECASE,
)
_DAYS = re.compile(r"(?P<num>\d+)\s*ngày", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.;!?])\s+|\n+")
_MANUAL_STRONG = ("ban giám đốc", "hội đồng")
_MANUAL = (
    "bắt buộc",
    "duyệt thủ công",
    "phê duyệt thủ công",
    "không được tự động",
    "không tự động",
    "phải được phê duyệt",
    "phải qua",
    "rủi ro cao",
) + _MANUAL_STRONG
_AUTO = ("tự động duyệt", "tự động phê duyệt", "duyệt tự động", "đối chiếu tự động")
_EVERY = ("mọi yêu cầu", "tất cả yêu cầu", "toàn bộ yêu cầu")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _money_value(num: str, unit: str) -> int | None:
    unit = _fold(unit)
    if unit in {"tỷ", "ty", "triệu", "trieu", "nghìn", "nghin", "ngàn"}:
        try:
            value = float(num.replace(",", "."))
        except ValueError:
            return None
        scale = {"tỷ": 1e9, "ty": 1e9, "triệu": 1e6, "trieu": 1e6}.get(unit, 1e3)
        return round(value * scale)
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits.isdigit() else None


def _lower_bound(sentence: str, start: int, end: int, value: int) -> int | None:
    """amount_gt for the number at [start:end] (strict '>' semantics)."""
    before = sentence[max(0, start - 25) : start]
    after = sentence[end : end + 15]
    if re.search(r"(dưới|không quá|tối đa|nhỏ hơn|thấp hơn)\s*$", before):
        return None  # upper bound: not expressible as a policy rule
    if re.search(r"(từ|tối thiểu|ít nhất|bằng hoặc lớn hơn)\s*$", before) or re.match(
        r"\s*trở lên", after
    ):
        return max(value - 1, 0)
    if re.search(r"(trên|vượt|vượt quá|quá|lớn hơn|cao hơn|hơn)\s*$", before):
        return value
    return None


def _threshold(pattern: re.Pattern, sentence: str, money: bool) -> int | None:
    for match in pattern.finditer(sentence):
        value = (
            _money_value(match.group("num"), match.group("unit"))
            if money
            else int(match.group("num"))
        )
        if value is None:
            continue
        bound = _lower_bound(sentence, match.start(), match.end(), value)
        if bound is not None:
            return bound
    return None


@dataclass(frozen=True)
class RequestTypeName:
    code: str
    name: str


def compile_regulations(
    regulations: list[dict[str, Any]], request_types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Extract enforceable approval rules from regulation sentences.

    A sentence becomes a rule when it carries an approval signal (forced manual
    review or explicit auto approval) and something to match on: an amount or
    day threshold, a named request type, or an explicit "mọi yêu cầu".
    """
    rules: list[dict[str, Any]] = []
    types = sorted(request_types, key=lambda t: -len(t.name))
    for reg in sorted(regulations, key=lambda r: r["code"]):
        sentences = [s.strip() for s in _SENTENCE.split(reg.get("content") or "")]
        for index, sentence in enumerate((s for s in sentences if s), start=1):
            low = _fold(sentence)
            manual = any(word in low for word in _MANUAL)
            auto = not manual and any(word in low for word in _AUTO)
            if not (manual or auto):
                continue
            amount_gt = _threshold(_MONEY, low, money=True)
            days_gt = _threshold(_DAYS, low, money=False)
            scoped = [t.code for t in types if t.name and _fold(t.name) in low]
            unconstrained = amount_gt is None and days_gt is None and not scoped
            if unconstrained and not any(word in low for word in _EVERY):
                continue
            base = {
                "description": sentence[:500],
                "amount_gt": amount_gt,
                "days_gt": days_gt,
            }
            if manual:
                base["min_risk"] = (
                    5 if any(word in low for word in _MANUAL_STRONG) else 4
                )
                base["auto_approve"] = False
            else:
                base["auto_approve"] = True
            rule_id = f"{reg['code']}-{index}"
            for code in scoped or [None]:
                rules.append(
                    {
                        "id": (f"{rule_id}-{code}" if code else rule_id)[:50],
                        "request_type": code,
                        **{k: v for k, v in base.items() if v is not None},
                    }
                )
    return rules


def snapshot_hash(regulations: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        sorted(
            (r["code"], r["title"], r.get("category") or "", r["content"])
            for r in regulations
        ),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 2. Announcement: what changed + how to work with the new process (pure)
# ---------------------------------------------------------------------------


def _vnd(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " đ"


def describe_rule(rule: dict[str, Any], type_names: dict[str, str]) -> str:
    scope = (
        f"Yêu cầu loại “{type_names.get(rule['request_type'], rule['request_type'])}”"
        if rule.get("request_type")
        else "Mọi yêu cầu"
    )
    conditions = []
    if rule.get("amount_gt") is not None:
        conditions.append(f"có giá trị từ {_vnd(rule['amount_gt'] + 1)} trở lên")
    if rule.get("days_gt") is not None:
        conditions.append(f"kéo dài từ {rule['days_gt'] + 1} ngày trở lên")
    head = scope + (" " + " và ".join(conditions) if conditions else "")
    if rule.get("auto_approve") is False:
        level = rule.get("min_risk") or 4
        return f"{head}: bắt buộc người duyệt xét thủ công (mức rủi ro tối thiểu {level}/5)."
    return f"{head}: được AI đối chiếu và có thể tự duyệt nếu đủ điều kiện."


def _rule_key(rule: dict[str, Any]) -> tuple:
    return tuple(
        rule.get(k)
        for k in ("request_type", "amount_gt", "days_gt", "min_risk", "auto_approve")
    )


def build_announcement(
    *,
    version: str,
    previous_regulations: list[dict[str, Any]],
    regulations: list[dict[str, Any]],
    previous_rules: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    type_names: dict[str, str],
) -> dict[str, Any]:
    old_regs = {r["code"]: r for r in previous_regulations}
    new_regs = {r["code"]: r for r in regulations}
    changes: list[dict[str, str]] = []
    for code in sorted(new_regs.keys() - old_regs.keys()):
        changes.append(
            {
                "kind": "REGULATION_ADDED",
                "title": f"Ban hành {code}: {new_regs[code]['title']}",
            }
        )
    for code in sorted(new_regs.keys() & old_regs.keys()):
        if (new_regs[code]["title"], new_regs[code]["content"]) != (
            old_regs[code]["title"],
            old_regs[code]["content"],
        ):
            changes.append(
                {
                    "kind": "REGULATION_UPDATED",
                    "title": f"Cập nhật {code}: {new_regs[code]['title']}",
                }
            )
    for code in sorted(old_regs.keys() - new_regs.keys()):
        changes.append(
            {
                "kind": "REGULATION_REMOVED",
                "title": f"Bãi bỏ {code}: {old_regs[code]['title']}",
            }
        )

    old_rules = {r["id"]: r for r in previous_rules}
    new_rules = {r["id"]: r for r in rules}
    guidance: list[dict[str, Any]] = []
    for rule_id in sorted(new_rules):
        rule = new_rules[rule_id]
        before = old_rules.get(rule_id)
        if before is not None and _rule_key(before) == _rule_key(rule):
            continue
        text = describe_rule(rule, type_names)
        changes.append(
            {"kind": "RULE_ADDED" if before is None else "RULE_CHANGED", "title": text}
        )
        if rule.get("auto_approve") is False:
            guidance.append(
                {
                    "title": text,
                    "steps": [
                        "Tạo yêu cầu như bình thường tại “Tạo yêu cầu mới”.",
                        "Yêu cầu thuộc trường hợp này sẽ không được tự động duyệt; hệ thống chuyển tới người phê duyệt theo quy trình.",
                        "Đính kèm đầy đủ chứng từ, giải trình ngay khi tạo để rút ngắn thời gian duyệt.",
                        "Theo dõi tiến độ và phản hồi yêu cầu bổ sung tại “Yêu cầu của tôi”.",
                    ],
                }
            )
    for rule_id in sorted(old_rules.keys() - new_rules.keys()):
        rule = old_rules[rule_id]
        text = describe_rule(rule, type_names)
        changes.append({"kind": "RULE_REMOVED", "title": f"Bãi bỏ luật: {text}"})
        if rule.get("auto_approve") is False:
            guidance.append(
                {
                    "title": f"Không còn bắt buộc duyệt thủ công: {text}",
                    "steps": [
                        "Yêu cầu thuộc trường hợp này nay được AI đối chiếu và có thể tự duyệt nếu đủ điều kiện.",
                        "Vẫn kiểm tra trạng thái tại “Yêu cầu của tôi”; người duyệt vẫn có thể yêu cầu bổ sung.",
                    ],
                }
            )

    added = sum(c["kind"] == "REGULATION_ADDED" for c in changes)
    updated = sum(c["kind"] == "REGULATION_UPDATED" for c in changes)
    removed = sum(c["kind"] == "REGULATION_REMOVED" for c in changes)
    summary = (
        f"Hệ thống đã áp dụng bộ quy định v{version}: {added} quy định mới, "
        f"{updated} quy định cập nhật, {removed} quy định bãi bỏ."
    )
    summary += (
        f" Có {len(guidance)} thay đổi về quy trình duyệt — xem hướng dẫn bên dưới."
        if guidance
        else " Quy trình thao tác của bạn không thay đổi."
    )
    return {
        "title": f"Hệ thống đã cập nhật quy định v{version}",
        "summary": summary,
        "changes": changes,
        "guidance": guidance,
    }


# ---------------------------------------------------------------------------
# 3. Lock state (derived from open jobs, short cache)
# ---------------------------------------------------------------------------


def _jobs_table_ready(cursor) -> bool:
    cursor.execute("SELECT to_regclass('eas.ai_learning_job') IS NOT NULL")
    return cursor.fetchone()[0] is True


_jobs_ready = {"value": None, "checked": 0.0}


def jobs_table_ready() -> bool:
    """Migration 12 applied? Cached per process (a miss is re-checked every 30 s)."""
    now = time.monotonic()
    if _jobs_ready["value"] is True or (
        _jobs_ready["value"] is False and now - _jobs_ready["checked"] < 30
    ):
        return bool(_jobs_ready["value"])
    try:
        with connection.cursor() as cursor:
            ready = _jobs_table_ready(cursor)
    except DatabaseError:
        ready = False
    _jobs_ready.update(value=ready, checked=now)
    return ready


def open_job_state() -> dict[str, Any] | None:
    """The open learning job (QUEUED/RUNNING), cached for a few seconds."""
    cached = cache.get(LOCK_CACHE_KEY)
    if cached is not None:
        return cached or None
    state: dict[str, Any] = {}
    try:
        with connection.cursor() as cursor:
            if _jobs_table_ready(cursor):
                cursor.execute(
                    """
                    SELECT id::text, status, step, step_label, progress, target_version,
                           (status = 'QUEUED' AND not_before <= statement_timestamp())
                           OR (status = 'RUNNING' AND lease_until < statement_timestamp())
                    FROM eas.ai_learning_job
                    WHERE status IN ('QUEUED', 'RUNNING')
                    """
                )
                row = cursor.fetchone()
                if row:
                    state = {
                        "job_id": row[0],
                        "status": row[1],
                        "step": max(int(row[2]), 1),
                        "step_label": row[3],
                        "progress": int(row[4]),
                        "target_version": row[5],
                        "claimable": bool(row[6]),
                    }
    except DatabaseError:
        logger.warning("ai_learning_state_unavailable", exc_info=True)
        return None
    cache.set(LOCK_CACHE_KEY, state, timeout=LOCK_CACHE_SECONDS)
    if state.get("claimable"):
        kick_runner()
    return state or None


def invalidate_lock_cache() -> None:
    cache.delete(LOCK_CACHE_KEY)


def steps_detail(current_step: int, failed: bool = False) -> list[dict[str, Any]]:
    out = []
    for step, label in STEP_LABELS.items():
        if failed and step == current_step:
            status = "FAILED"
        elif step < current_step or (step == 4 and current_step >= 4 and not failed):
            status = "DONE"
        elif step == current_step:
            status = "RUNNING"
        else:
            status = "WAITING"
        out.append(
            {
                "step": step,
                "code": STEP_STATUS[step],
                "label": label,
                "status": status,
                "percent": step * 25,
            }
        )
    return out


# ---------------------------------------------------------------------------
# 4. Enqueue
# ---------------------------------------------------------------------------


def enqueue_learning(cursor, *, reason: str, requested_by: str | None) -> str | None:
    """Queue (or re-arm) the learning job inside the caller's transaction."""
    if not _jobs_table_ready(cursor):
        logger.warning("ai_learning_job missing: run migration 12")
        return None
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('eas.ai_learning_job'))")
    cursor.execute(
        """
        SELECT COALESCE(global_major_version, 1) || '.' || COALESCE(global_minor_version, 0),
               active_regulation_version
        FROM eas.ai_system_state WHERE id = 1
        """
    )
    row = cursor.fetchone() or ("1.0", None)
    target, base = row[0], row[1]
    cursor.execute(
        """
        UPDATE eas.ai_learning_job
        SET target_version = %s,
            reason = left(reason || ' | ' || %s, 2000),
            rerun_requested = (status = 'RUNNING'),
            updated_at = statement_timestamp()
        WHERE status IN ('QUEUED', 'RUNNING')
        RETURNING id::text
        """,
        [target, reason],
    )
    existing = cursor.fetchone()
    if existing:
        job_id = existing[0]
    else:
        cursor.execute(
            """
            INSERT INTO eas.ai_learning_job (target_version, base_version, reason, requested_by, step, step_label)
            VALUES (%s, %s, %s, %s, 1, 'Đang chờ AI học quy định')
            RETURNING id::text
            """,
            [target, base, reason[:2000], requested_by],
        )
        job_id = cursor.fetchone()[0]
    cursor.execute(
        """
        UPDATE eas.ai_system_state
        SET target_regulation_version = %s, sync_status = 'SYNCING', current_step_index = 1,
            progress_percent = 0, current_step_label = 'Đang chờ AI học quy định',
            steps_detail = %s, updated_at = now()
        WHERE id = 1
        """,
        [target, Jsonb(steps_detail(1))],
    )
    transaction.on_commit(_after_enqueue_commit)
    return job_id


def _after_enqueue_commit() -> None:
    invalidate_lock_cache()
    kick_runner()


# ---------------------------------------------------------------------------
# 5. Runner
# ---------------------------------------------------------------------------

_runner_guard = threading.Lock()


def kick_runner() -> None:
    """Best-effort in-process runner; leases make it safe to die mid-way."""
    if (
        os.getenv("EAS_ENV", "").lower() == "test"
        or getattr(settings, "ENVIRONMENT", "") == "test"
    ):
        return
    if not _runner_guard.acquire(blocking=False):
        return

    def _run() -> None:
        try:
            run_pending()
        except Exception:
            logger.exception("ai_learning_runner_failed")
        finally:
            connection.close()
            _runner_guard.release()

    threading.Thread(target=_run, name="eas-ai-learning", daemon=True).start()


def _owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"


def claim_job(owner: str) -> dict[str, Any] | None:
    with transaction.atomic(), connection.cursor() as cursor:
        if not _jobs_table_ready(cursor):
            return None
        cursor.execute(
            """
            UPDATE eas.ai_learning_job j
            SET status = 'RUNNING', attempts = attempts + 1, lease_owner = %s,
                lease_until = statement_timestamp() + make_interval(secs => %s),
                started_at = COALESCE(started_at, statement_timestamp()),
                updated_at = statement_timestamp(), error = NULL
            WHERE j.id = (
              SELECT id FROM eas.ai_learning_job
              WHERE (status = 'QUEUED' AND not_before <= statement_timestamp())
                 OR (status = 'RUNNING' AND lease_until < statement_timestamp())
              ORDER BY created_at
              LIMIT 1
              FOR UPDATE SKIP LOCKED
            )
            RETURNING id::text, target_version, attempts, max_attempts
            """,
            [owner, LEASE_SECONDS],
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "target_version": row[1],
        "attempts": row[2],
        "max_attempts": row[3],
    }


def _progress(job_id: str, owner: str, step: int, label: str) -> None:
    """Record progress and extend the lease; raise if another runner took over."""
    progress = {1: 15, 2: 45, 3: 75, 4: 100}[step]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE eas.ai_learning_job
            SET step = %s, step_label = %s, progress = %s,
                lease_until = statement_timestamp() + make_interval(secs => %s),
                updated_at = statement_timestamp()
            WHERE id = %s AND status = 'RUNNING' AND lease_owner = %s
            """,
            [step, label, progress, LEASE_SECONDS, job_id, owner],
        )
        if cursor.rowcount != 1:
            raise RuntimeError("lease lost")
        cursor.execute(
            """
            UPDATE eas.ai_system_state
            SET sync_status = %s, current_step_index = %s, progress_percent = %s,
                current_step_label = %s, steps_detail = %s, updated_at = now()
            WHERE id = 1
            """,
            [
                STEP_STATUS[step] if step < 4 else "APPLYING",
                step,
                progress,
                label,
                Jsonb(steps_detail(step)),
            ],
        )
    invalidate_lock_cache()


def _load_inputs(
    cursor,
) -> tuple[list[dict[str, Any]], list[RequestTypeName], dict[str, Any]]:
    cursor.execute(
        """
        SELECT code, title, category, content, version_string
        FROM eas.company_regulations WHERE NOT is_deleted ORDER BY code
        """
    )
    regulations = [
        {
            "code": r[0],
            "title": r[1],
            "category": r[2],
            "content": r[3] or "",
            "version": r[4],
        }
        for r in cursor.fetchall()
    ]
    cursor.execute("SELECT code, name FROM eas.request_type WHERE is_active")
    types = [RequestTypeName(code=r[0], name=r[1] or "") for r in cursor.fetchall()]
    cursor.execute(
        """
        SELECT COALESCE(applied_policy, '{}'::jsonb), COALESCE(applied_snapshot, '[]'::jsonb)
        FROM eas.ai_system_state WHERE id = 1
        """
    )
    row = cursor.fetchone() or ({}, [])
    return regulations, types, {"policy": row[0] or {}, "snapshot": row[1] or []}


def _manual_rules(cursor) -> list[dict[str, Any]]:
    """Rules authored in the AI policy screen (eas.ai_policy_version, migration 08)."""
    cursor.execute("SELECT to_regclass('eas.ai_policy_version') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return []
    cursor.execute("SELECT document FROM eas.ai_policy_version WHERE state = 'ACTIVE'")
    row = cursor.fetchone()
    rules = (row[0] or {}).get("rules", []) if row else []
    return [r for r in rules if isinstance(r, dict) and r.get("id")]


def _ai_http():
    import httpx

    return httpx.Client(
        base_url=settings.EAS_AI_SERVICE_URL,
        headers={"X-Internal-Secret": settings.EAS_AI_INTERNAL_SECRET},
        timeout=httpx.Timeout(8.0, connect=3.0),
    )


def apply_to_ai(policy: dict[str, Any]) -> dict[str, Any]:
    """Push the policy to ai_service and prove the engine enforces it."""
    import httpx

    try:
        with _ai_http() as client:
            pushed = client.post("/ai/policy/rules", json=policy)
            if pushed.status_code >= 500:
                raise TransientLearningError(f"AI service HTTP {pushed.status_code}")
            if pushed.status_code != 200:
                raise RuntimeError(
                    f"AI service rejected policy: HTTP {pushed.status_code}"
                )
            current = client.get("/ai/policy/rules").json() or {}
            if current.get("version") != policy["version"] or len(
                current.get("rules", [])
            ) != len(policy["rules"]):
                raise RuntimeError("AI service did not load the new policy")
            checks = 0
            for rule in policy["rules"]:
                if rule.get("auto_approve") is not False:
                    continue
                probe = {
                    "request_id": str(uuid4()),
                    "request_type": rule.get("request_type") or "POLICY_PROBE",
                    "lifecycle_template": "A",
                    "risk_score": 1,
                    "amount": float((rule.get("amount_gt") or 0) + 1),
                    "days_requested": int((rule.get("days_gt") or 0) + 1),
                    "requester_name": "EAS policy verifier",
                    "requester_dept": "QA",
                }
                decision = client.post("/ai/auto-approve/evaluate", json=probe).json()
                reasons = " ".join(decision.get("detail_reasons") or [])
                if (
                    decision.get("decision") != "escalate_to_human"
                    or decision.get("policy_version") != policy["version"]
                    or rule["id"] not in reasons
                ):
                    raise RuntimeError(
                        f"Rule {rule['id']} is not enforced by the AI engine"
                    )
                checks += 1
                if checks >= 5:
                    break
            return {"rules_loaded": len(policy["rules"]), "enforcement_checks": checks}
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        raise TransientLearningError(
            f"AI service unreachable: {type(exc).__name__}"
        ) from exc


def _restore_previous(previous_policy: dict[str, Any]) -> None:
    if not previous_policy.get("version"):
        return
    try:
        with _ai_http() as client:
            client.post("/ai/policy/rules", json=previous_policy)
    except Exception:
        logger.warning("ai_policy_restore_failed", exc_info=True)


def _finish_applied(job: dict[str, Any], owner: str, result: dict[str, Any]) -> bool:
    """Commit the new policy. Returns False when a rerun was requested instead."""
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT rerun_requested, target_version FROM eas.ai_learning_job WHERE id = %s AND lease_owner = %s FOR UPDATE",
            [job["id"], owner],
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("lease lost")
        if row[0]:
            cursor.execute(
                """
                UPDATE eas.ai_learning_job
                SET status = 'QUEUED', rerun_requested = false, attempts = 0, lease_owner = NULL,
                    lease_until = NULL, step = 1, progress = 0, not_before = statement_timestamp(),
                    step_label = 'Có thay đổi mới, AI học lại', updated_at = statement_timestamp()
                WHERE id = %s
                """,
                [job["id"]],
            )
            return False
        version = result["version"]
        cursor.execute(
            """
            UPDATE eas.ai_system_state
            SET applied_policy = %s, applied_snapshot = %s, applied_at = now(), applied_job_id = %s,
                active_regulation_version = %s, target_regulation_version = %s,
                sync_status = 'COMPLETED', current_step_index = 4, progress_percent = 100,
                current_step_label = %s, client_maintenance_lock = false, steps_detail = %s,
                updated_at = now()
            WHERE id = 1
            """,
            [
                Jsonb(result["policy"]),
                Jsonb(result["snapshot"]),
                job["id"],
                version,
                version,
                f"Đã áp dụng quy định v{version}",
                Jsonb(steps_detail(4)),
            ],
        )
        announcement = result["announcement"]
        cursor.execute(
            """
            INSERT INTO eas.system_announcement (job_id, version, title, summary, changes, guidance)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO NOTHING
            """,
            [
                job["id"],
                version,
                announcement["title"],
                announcement["summary"],
                Jsonb(announcement["changes"]),
                Jsonb(announcement["guidance"]),
            ],
        )
        cursor.execute(
            """
            INSERT INTO eas.system_versions_changelog (system_version, change_type, change_scope, title, description, new_value, changed_by)
            VALUES (%s, 'REGULATION', %s, %s, %s, %s, 'AI learning job')
            """,
            [
                f"v{version}",
                "MINOR" if version.split(".")[-1] != "0" else "MAJOR",
                announcement["title"],
                announcement["summary"],
                Jsonb(
                    {"rules": len(result["policy"]["rules"]), **result["verification"]}
                ),
            ],
        )
        cursor.execute(
            """
            UPDATE eas.ai_learning_job
            SET status = 'APPLIED', step = 4, progress = 100, step_label = %s,
                compiled_policy = %s, diff = %s, finished_at = statement_timestamp(),
                lease_owner = NULL, lease_until = NULL, updated_at = statement_timestamp()
            WHERE id = %s
            """,
            [
                f"Đã áp dụng quy định v{version}",
                Jsonb(result["policy"]),
                Jsonb(announcement["changes"]),
                job["id"],
            ],
        )
    invalidate_lock_cache()
    return True


def _fail(job: dict[str, Any], owner: str, error: str, *, retry: bool) -> None:
    final = not retry or job["attempts"] >= job["max_attempts"]
    with transaction.atomic(), connection.cursor() as cursor:
        if not final:
            delay = RETRY_BACKOFF_SECONDS[
                min(job["attempts"], len(RETRY_BACKOFF_SECONDS)) - 1
            ]
            cursor.execute(
                """
                UPDATE eas.ai_learning_job
                SET status = 'QUEUED', lease_owner = NULL, lease_until = NULL, error = %s,
                    not_before = statement_timestamp() + make_interval(secs => %s),
                    step_label = %s, updated_at = statement_timestamp()
                WHERE id = %s AND lease_owner = %s
                """,
                [
                    error[:2000],
                    delay,
                    f"Thử lại sau {delay} giây: {error[:120]}",
                    job["id"],
                    owner,
                ],
            )
        else:
            cursor.execute(
                """
                UPDATE eas.ai_learning_job
                SET status = 'FAILED', error = %s, finished_at = statement_timestamp(),
                    lease_owner = NULL, lease_until = NULL, step_label = 'Thất bại: giữ bộ luật cũ',
                    updated_at = statement_timestamp()
                WHERE id = %s
                RETURNING step
                """,
                [error[:2000], job["id"]],
            )
            step = (cursor.fetchone() or (3,))[0]
            cursor.execute(
                """
                UPDATE eas.ai_system_state
                SET sync_status = 'ERROR', current_step_index = %s, client_maintenance_lock = false,
                    current_step_label = %s, steps_detail = %s, updated_at = now()
                WHERE id = 1
                """,
                [
                    max(step, 1),
                    f"AI chưa học được quy định v{job['target_version']}: giữ bộ luật cũ",
                    Jsonb(steps_detail(max(step, 1), failed=True)),
                ],
            )
            cursor.execute(
                """
                INSERT INTO eas.system_announcement (job_id, audience, kind, version, title, summary, changes, guidance)
                VALUES (%s, 'ADMIN', 'REGULATION_UPDATE_FAILED', %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
                ON CONFLICT (job_id) DO NOTHING
                """,
                [
                    job["id"],
                    job["target_version"],
                    f"AI chưa áp dụng được quy định v{job['target_version']}",
                    f"Sau {job['attempts']} lần thử, AI chưa học được bộ quy định mới; hệ thống giữ bộ luật đang hiệu lực và đã mở khoá đăng nhập. Lỗi: {error[:300]}. Kiểm tra AI service rồi bấm “Học lại” trong Quản trị AI.",
                ],
            )
    invalidate_lock_cache()


def process_job(job: dict[str, Any], owner: str) -> str:
    previous: dict[str, Any] = {}
    try:
        _progress(job["id"], owner, 1, STEP_LABELS[1])
        with connection.cursor() as cursor:
            regulations, types, previous = _load_inputs(cursor)
            manual = _manual_rules(cursor)
        version = job["target_version"].lstrip("v")
        _progress(job["id"], owner, 2, STEP_LABELS[2])
        compiled = compile_regulations(regulations, types)
        seen = {r["id"] for r in manual}
        policy = {
            "version": f"v{version}",
            "rules": manual + [r for r in compiled if r["id"] not in seen],
        }
        snapshot = [
            {
                "code": r["code"],
                "title": r["title"],
                "content": r["content"],
                "version": r["version"],
            }
            for r in regulations
        ]
        _progress(job["id"], owner, 3, STEP_LABELS[3])
        verification = apply_to_ai(policy)
        announcement = build_announcement(
            version=version,
            previous_regulations=previous["snapshot"],
            regulations=snapshot,
            previous_rules=(previous["policy"] or {}).get("rules", []),
            rules=policy["rules"],
            type_names={t.code: t.name for t in types},
        )
        applied = _finish_applied(
            job,
            owner,
            {
                "version": version,
                "policy": policy,
                "snapshot": snapshot,
                "announcement": announcement,
                "verification": verification,
            },
        )
        return "APPLIED" if applied else "REQUEUED"
    except TransientLearningError as exc:
        _fail(job, owner, str(exc), retry=True)
        return "RETRY"
    except Exception as exc:
        logger.exception("ai_learning_job_failed")
        _restore_previous((previous or {}).get("policy") or {})
        _fail(
            job,
            owner,
            f"{type(exc).__name__}: {exc}",
            retry=job["attempts"] < job["max_attempts"],
        )
        return "FAILED"


def run_pending(*, max_jobs: int = 3) -> int:
    """Claim and process due jobs. Safe to call from any process."""
    done = 0
    owner = _owner()
    for _ in range(max_jobs):
        job = claim_job(owner)
        if job is None:
            break
        process_job(job, owner)
        done += 1
    return done


# ---------------------------------------------------------------------------
# 6. Announcements for users
# ---------------------------------------------------------------------------


def list_announcements(
    actor, *, unread_only: bool, limit: int = 20
) -> list[dict[str, Any]]:
    audience = ["ALL", "ADMIN"] if actor.roles & ADMIN_ROLES else ["ALL"]
    with connection.cursor() as cursor:
        if not _jobs_table_ready(cursor):
            return []
        cursor.execute(
            """
            SELECT a.id::text, a.kind, a.version, a.title, a.summary, a.changes, a.guidance,
                   a.created_at, r.read_at
            FROM eas.system_announcement a
            LEFT JOIN eas.announcement_receipt r ON r.announcement_id = a.id AND r.user_id = %s
            WHERE a.audience = ANY(%s)
              AND a.created_at >= (SELECT created_at FROM eas.app_user WHERE id = %s) - interval '30 days'
              AND (NOT %s OR r.read_at IS NULL)
            ORDER BY a.created_at DESC
            LIMIT %s
            """,
            [actor.id, audience, actor.id, unread_only, limit],
        )
        rows = cursor.fetchall()
    return [
        {
            "id": r[0],
            "kind": r[1],
            "version": r[2],
            "title": r[3],
            "summary": r[4],
            "changes": r[5],
            "guidance": r[6],
            "created_at": r[7].isoformat(),
            "read_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


def mark_announcement_read(actor, announcement_id: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO eas.announcement_receipt (announcement_id, user_id)
            SELECT id, %s FROM eas.system_announcement WHERE id = %s
            ON CONFLICT DO NOTHING
            """,
            [actor.id, announcement_id],
        )
        cursor.execute(
            "SELECT 1 FROM eas.system_announcement WHERE id = %s", [announcement_id]
        )
        return cursor.fetchone() is not None
