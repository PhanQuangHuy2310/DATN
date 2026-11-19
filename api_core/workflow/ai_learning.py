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
import socket
import threading
import time
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


class RegulationRejected(RuntimeError):
    """Văn bản thay đổi có lỗi chặn (lỗi ký tự, mâu thuẫn): không học, trả lại đúng các văn bản lỗi (migration 26)."""

    def __init__(self, checks: dict[str, dict[str, Any]]):
        self.checks = checks
        super().__init__("regulation validation failed")


# ---------------------------------------------------------------------------
# 1. Regulation compiler: Vietnamese text -> policy rules (pure functions)
#    Cài đặt ở regulation_compiler.py (v2: điều kiện ngữ cảnh deadline / lặp lại /
#    chia nhỏ, tách "hoặc", không chặn tràn khi điều kiện ngoài schema).
# ---------------------------------------------------------------------------

from api_core.workflow.regulation_compiler import (
    RequestTypeName,
    compile_regulations,
)
from api_core.workflow.regulation_compiler import (
    rule_key as _compiled_rule_key,
)


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


_WINDOW_TEXT = {
    "CALENDAR_MONTH": "trong tháng",
    "ROLLING_7D": "trong 7 ngày",
    "ROLLING_30D": "trong 30 ngày",
}


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
    if rule.get("due_within_hours"):
        text = (
            f"khi người gửi đang giữ việc đến hạn trong {rule['due_within_hours']} giờ"
        )
        if rule.get("require_no_handover"):
            text += " mà chưa chỉ định người nhận bàn giao"
        conditions.append(text)
    if rule.get("repeat_count_gte"):
        window = _WINDOW_TEXT.get(rule.get("repeat_window") or "ROLLING_30D", "")
        conditions.append(f"từ lần thứ {rule['repeat_count_gte']} {window}".rstrip())
    if rule.get("split_suspect"):
        total = rule.get("split_total_gt")
        conditions.append(
            "có dấu hiệu chia nhỏ hồ sơ tài chính"
            + (f" (tổng 7 ngày vượt {_vnd(int(total))})" if total else "")
        )
    head = scope + (" " + " và ".join(conditions) if conditions else "")
    if rule.get("auto_approve") is False:
        level = rule.get("min_risk") or 4
        tail = f"bắt buộc người duyệt xét thủ công (mức rủi ro tối thiểu {level}/5)"
        if rule.get("escalate_to"):
            tail += f", hồ sơ được chuyển sang quy trình {rule['escalate_to']}"
        return f"{head}: {tail}."
    return f"{head}: được AI đối chiếu và có thể tự duyệt nếu đủ điều kiện."


def _rule_key(rule: dict[str, Any]) -> tuple:
    return (*_compiled_rule_key(rule), rule.get("min_risk"), rule.get("escalate_to"))


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
    cache.delete("eas:public:ai_status")


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
            client_maintenance_lock = true,
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
        if getattr(connection, "vendor", None) == "postgresql":
            cursor.execute(
                """
                SELECT to_regclass('eas.ai_policy_version') IS NULL
                    OR has_table_privilege('eas.ai_policy_version', 'SELECT')
                """
            )
            can_read_policy = cursor.fetchone()
            if can_read_policy and not can_read_policy[0]:
                logger.warning("skip_claim_ai_learning_missing_policy_select_privilege")
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
    cursor.execute("SELECT code, name, lifecycle FROM eas.request_type WHERE is_active")
    types = [
        RequestTypeName(
            code=r[0], name=r[1] or "", lifecycle=(r[2] or "").strip() or None
        )
        for r in cursor.fetchall()
    ]
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


def enforcement_probe(rule: dict[str, Any]) -> dict[str, Any]:
    """A synthetic request that satisfies every condition of ``rule`` (incl. context)."""
    window_field = {
        "CALENDAR_MONTH": "same_type_count_month",
        "ROLLING_7D": "same_type_count_7d",
        "ROLLING_30D": "same_type_count_30d",
    }
    probe: dict[str, Any] = {
        "request_id": str(uuid4()),
        "request_type": rule.get("request_type") or "POLICY_PROBE",
        "lifecycle_template": "A",
        "risk_score": 1,
        "amount": float((rule.get("amount_gt") or 0) + 1),
        "days_requested": int((rule.get("days_gt") or 0) + 1),
        "requester_name": "EAS policy verifier",
        "requester_dept": "QA",
    }
    if rule.get("due_within_hours"):
        probe["open_work_due_hours"] = [1.0]
        probe["handover_assigned"] = False
    if rule.get("repeat_count_gte"):
        count = int(rule["repeat_count_gte"])
        probe[window_field[rule.get("repeat_window") or "ROLLING_30D"]] = count
        probe["attendance_count_30d"] = count
    if rule.get("split_suspect"):
        total = float(rule.get("split_total_gt") or 20_000_000)
        probe["amount"] = total
        probe["requester_amount_7d"] = total * 2 + 1
        probe["requester_finance_count_7d"] = 3
    # v3: cận trên, phần trăm, địa điểm, ngày đã quá N ngày, cửa sổ đếm khác 7/30 ngày/tháng.
    if rule.get("amount_lte") is not None:
        low = float(rule.get("amount_gt") or 0)
        probe["amount"] = (
            float(rule["amount_lte"])
            if low + 1 > rule["amount_lte"]
            else min(low + 1, rule["amount_lte"])
        )
    if rule.get("days_lte") is not None:
        probe["days_requested"] = int(
            min((rule.get("days_gt") or 0) + 1, rule["days_lte"])
        )
    if rule.get("percent_gt") is not None or rule.get("percent_lte") is not None:
        low = float(
            rule.get("percent_gt") if rule.get("percent_gt") is not None else -1
        )
        probe["percent"] = (
            min(low + 1, float(rule["percent_lte"]))
            if rule.get("percent_lte") is not None
            else low + 1
        )
    if rule.get("location_contains"):
        probe["location_text"] = rule["location_contains"]
    if rule.get("retro_days_gt") is not None:
        probe["notice_hours"] = -24.0 * (int(rule["retro_days_gt"]) + 1)
    if (
        rule.get("repeat_count_gte")
        and (rule.get("repeat_window") or "ROLLING_30D") not in window_field
    ):
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _Zone

        today = _dt.now(_Zone("Asia/Ho_Chi_Minh")).date().isoformat()
        probe["same_type_dates"] = [today] * (int(rule["repeat_count_gte"]) - 1)
    return probe


def _verifiable(rule: dict[str, Any]) -> bool:
    """Luật đang có hiệu lực hôm nay và không có vùng loại trừ (hồ sơ thử có thể rơi vào vùng đó)."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _Zone

    today = _dt.now(_Zone("Asia/Ho_Chi_Minh")).date().isoformat()
    if rule.get("effective_from") and rule["effective_from"] > today:
        return False
    if rule.get("effective_until") and rule["effective_until"] < today:
        return False
    return not rule.get("exclude")


def apply_to_ai(policy: dict[str, Any]) -> dict[str, Any]:
    """Push the policy to ai_service and prove the engine enforces it."""
    import httpx

    try:
        with _ai_http() as client:
            pushed = client.post(
                "/ai/policy/rules",
                json={"version": policy["version"], "rules": policy["rules"]},
            )
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
                if rule.get("auto_approve") is not False or not _verifiable(rule):
                    continue
                probe = enforcement_probe(rule)
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
            client.post(
                "/ai/policy/rules",
                json={
                    "version": previous_policy["version"],
                    "rules": previous_policy.get("rules") or [],
                },
            )
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
        if announcement.get("changes"):
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
        from api_core.workflow.service import record_system_change

        record_system_change(
            cursor,
            actor_id=None,
            change_type="REGULATION",
            change_scope="MINOR" if version.split(".")[-1] != "0" else "MAJOR",
            system_version=f"v{version}",
            title=announcement["title"],
            description=announcement["summary"],
            new_value={
                "rules": len(result["policy"]["rules"]),
                **result["verification"],
            },
            target_type="ai_learning_job",
            target_id=str(job["id"]),
            extra_details={"changed_by": "AI learning job"},
            correlation_id=str(uuid4()),
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
            # Trả lại mọi thay đổi chưa áp dụng được: hiệu lực (văn bản + bộ luật) quay về bản đã áp dụng (migration 26).
            from api_core.workflow import regulation_rejection as rejection

            rejected = []
            try:
                with transaction.atomic():
                    rejected = (
                        rejection.rollback_to_applied(
                            cursor, job_id=job["id"], cause="TECHNICAL", message=error
                        )
                        or []
                    )
            except (
                Exception
            ):  # khôi phục lỗi không được làm treo tác vụ: giữ cách cũ, vẫn báo admin
                logger.exception("regulation_rollback_failed job=%s", job["id"])
                rejected = []
            cursor.execute(
                """
                UPDATE eas.ai_system_state
                SET sync_status = %s, current_step_index = %s, client_maintenance_lock = false,
                    current_step_label = %s, steps_detail = %s, updated_at = now()
                WHERE id = 1
                """,
                [
                    "COMPLETED" if rejected else "ERROR",
                    max(step, 1),
                    f"Đã trả lại {', '.join(r['code'] for r in rejected)}: giữ bản đã áp dụng"
                    if rejected
                    else f"AI chưa học được quy định v{job['target_version']}: giữ bộ luật cũ",
                    Jsonb(steps_detail(max(step, 1), failed=True)),
                ],
            )
            changes, guidance = [], []
            if rejected:
                title, summary, changes, guidance = rejection.announcement_text(
                    rejected, "TECHNICAL", error
                )
            else:
                title = f"AI chưa áp dụng được quy định v{job['target_version']}"
                summary = (
                    f"Sau {job['attempts']} lần thử, AI chưa học được bộ quy định mới; hệ thống giữ bộ luật đang "
                    f"hiệu lực và đã mở khoá đăng nhập. Lỗi: {error[:300]}. Kiểm tra AI service rồi bấm "
                    "\u201cHọc lại\u201d trong Quản trị AI."
                )
            cursor.execute(
                """
                INSERT INTO eas.system_announcement (job_id, audience, kind, version, title, summary, changes, guidance)
                VALUES (%s, 'ADMIN', %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING
                """,
                [
                    job["id"],
                    "REGULATION_REJECTED" if rejected else "REGULATION_UPDATE_FAILED",
                    job["target_version"],
                    title,
                    summary,
                    Jsonb(changes),
                    Jsonb(guidance),
                ],
            )
    invalidate_lock_cache()


def _reject(job: dict[str, Any], owner: str, checks: dict[str, dict[str, Any]]) -> str:
    """Trả lại các văn bản có lỗi chặn và báo admin; còn thay đổi hợp lệ khác thì học lại ngay phần đó."""
    from api_core.workflow import regulation_rejection as rejection
    from api_core.workflow.regulation_validation import summary_text

    bad = {code: r for code, r in checks.items() if not r["ok"]}
    message = "; ".join(f"{code}: {summary_text(r, 2)}" for code, r in bad.items())
    with transaction.atomic(), connection.cursor() as cursor:
        rejected = rejection.rollback_to_applied(
            cursor,
            job_id=job["id"],
            cause="VALIDATION",
            message=message,
            validation=checks,
            only_codes=set(bad),
        )
    if not rejected:  # chưa có migration 26 hoặc chưa từng áp dụng: giữ cách cũ (thất bại, giữ bộ luật cũ)
        _fail(job, owner, f"Văn bản quy định có lỗi: {message}", retry=False)
        return "FAILED"
    with transaction.atomic(), connection.cursor() as cursor:
        regulations, _types, previous = _load_inputs(cursor)
        remaining = rejection.changes(regulations, previous["snapshot"])
        if remaining:
            # Văn bản khác trong cùng đợt không lỗi: học lại ngay phần đó (vẫn giữ khoá bảo trì).
            cursor.execute(
                """
                UPDATE eas.ai_learning_job
                SET status = 'QUEUED', rerun_requested = false, attempts = 0, lease_owner = NULL,
                    lease_until = NULL, step = 1, progress = 0, not_before = statement_timestamp(), error = %s,
                    step_label = 'Đã trả lại văn bản lỗi, AI học phần còn lại', updated_at = statement_timestamp()
                WHERE id = %s
                """,
                [message[:2000], job["id"]],
            )
            announce_job = None
        else:
            cursor.execute(
                """
                UPDATE eas.ai_learning_job
                SET status = 'FAILED', error = %s, diff = %s, finished_at = statement_timestamp(),
                    lease_owner = NULL, lease_until = NULL,
                    step_label = 'Trả lại văn bản lỗi, giữ bản đã áp dụng', updated_at = statement_timestamp()
                WHERE id = %s
                """,
                [message[:2000], Jsonb(rejected), job["id"]],
            )
            cursor.execute(
                """
                UPDATE eas.ai_system_state
                SET sync_status = 'COMPLETED', current_step_index = 2, client_maintenance_lock = false,
                    current_step_label = %s, steps_detail = %s, updated_at = now()
                WHERE id = 1
                """,
                [
                    f"Đã trả lại {', '.join(r['code'] for r in rejected)}: văn bản có lỗi",
                    Jsonb(steps_detail(2, failed=True)),
                ],
            )
            announce_job = job["id"]
        title, summary, changes, guidance = rejection.announcement_text(
            rejected, "VALIDATION", message
        )
        cursor.execute(
            """
            INSERT INTO eas.system_announcement (job_id, audience, kind, version, title, summary, changes, guidance)
            VALUES (%s, 'ADMIN', 'REGULATION_REJECTED', %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO NOTHING
            """,
            [
                announce_job,
                job["target_version"],
                title,
                summary,
                Jsonb(changes),
                Jsonb(guidance),
            ],
        )
    invalidate_lock_cache()
    return "REJECTED"


RULE_KEYS = {
    "request_type",
    "amount_gt",
    "days_gt",
    "due_within_hours",
    "require_no_handover",
    "repeat_count_gte",
    "repeat_window",
    "split_suspect",
    "split_total_gt",
    "min_risk",
    "auto_approve",
    "escalate_to",
    "approvers",
}


def validate_review_rules(rules: Any, type_codes: set[str]) -> list[dict[str, Any]]:
    """Luật admin duyệt cho một câu: cùng schema với trình biên dịch v2 / PolicyRule của AI service."""
    if not isinstance(rules, list) or not 1 <= len(rules) <= 10:
        raise ValueError("Cần 1-10 luật")
    clean = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - RULE_KEYS:
            raise ValueError("Trường luật không hợp lệ")
        code = rule.get("request_type")
        if code is not None and code not in type_codes:
            raise ValueError(f"Mã loại không có: {code}")
        for key in (
            "amount_gt",
            "days_gt",
            "due_within_hours",
            "repeat_count_gte",
            "split_total_gt",
            "min_risk",
        ):
            value = rule.get(key)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise ValueError(f"{key} phải là số không âm")
        if rule.get("min_risk") is not None and not 1 <= rule["min_risk"] <= 5:
            raise ValueError("min_risk phải từ 1 đến 5")
        if rule.get("auto_approve") not in (True, False):
            raise ValueError("Cần auto_approve true/false")
        if rule.get("repeat_window") not in (
            None,
            "CALENDAR_MONTH",
            "ROLLING_7D",
            "ROLLING_30D",
        ):
            raise ValueError("repeat_window không hợp lệ")
        if rule.get("escalate_to") not in (None, "B", "C"):
            raise ValueError("escalate_to chỉ B hoặc C")
        if rule["auto_approve"] and any(
            rule.get(k)
            for k in ("due_within_hours", "repeat_count_gte", "split_suspect")
        ):
            raise ValueError("Điều kiện ngữ cảnh chỉ được dùng để chặn tự duyệt")
        out = {k: v for k, v in rule.items() if v is not None}
        if out["auto_approve"] is False:
            out.setdefault("min_risk", 4)
        clean.append(out)
    return clean


def _suggest_rules(sentence: str, types: list[RequestTypeName]) -> dict[str, Any]:
    try:
        with _ai_http() as client:
            resp = client.post(
                "/ai/regulation-llm/rules",
                json={
                    "clause": sentence,
                    "types": [
                        {"code": t.code, "name": t.name, "lifecycle": t.lifecycle}
                        for t in types
                    ],
                },
                timeout=30.0,
            )
            data = (
                resp.json()
                if resp.status_code == 200
                else {"error": f"HTTP {resp.status_code}"}
            )
    except Exception as exc:  # noqa: BLE001 - gợi ý của Gemini là phụ, câu vẫn vào hàng chờ
        data = {"error": type(exc).__name__}
    return {
        k: data.get(k)
        for k in ("rules", "rejected", "error", "model", "engine")
        if data.get(k) is not None
    }


def clause_review_cycle(
    regulations: list[dict[str, Any]], types: list[RequestTypeName]
) -> list[dict[str, Any]]:
    """Đưa câu chưa hiểu lên hàng chờ của admin; trả các luật admin đã duyệt cho câu còn hiệu lực."""
    from api_core.workflow.regulation_compiler import sentences, skip_reason

    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('eas.regulation_clause_review') IS NOT NULL")
        if not cursor.fetchone()[0]:
            return []
        current: dict[tuple[str, str], str] = {}
        for reg in regulations:
            for sentence in sentences(reg.get("content") or ""):
                current[
                    (reg["code"], hashlib.sha256(sentence.encode("utf-8")).hexdigest())
                ] = sentence
        cursor.execute(
            "SELECT regulation_code, sentence_sha256 FROM eas.regulation_clause_review"
        )
        known = {(r[0], r[1]) for r in cursor.fetchall()}
    for (code, sha), sentence in current.items():
        if (code, sha) in known:
            continue
        reason = skip_reason(sentence, types)
        if reason is None:
            continue
        suggestion = _suggest_rules(sentence, types)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO eas.regulation_clause_review(regulation_code, sentence, sentence_sha256, reason, suggestion)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (regulation_code, sentence_sha256) DO NOTHING
                """,
                [code, sentence[:2000], sha, reason[:200], Jsonb(suggestion)],
            )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, regulation_code, sentence_sha256, sentence, approved_rules
            FROM eas.regulation_clause_review WHERE state = 'APPROVED' ORDER BY decided_at
            """
        )
        approved = cursor.fetchall()
    rules = []
    for review_id, code, sha, sentence, approved_rules in approved:
        if (code, sha) not in current:
            continue  # câu đã bị sửa/xóa khỏi quy định: luật duyệt cho câu cũ không còn hiệu lực
        for index, rule in enumerate(approved_rules or [], start=1):
            rules.append(
                {
                    **rule,
                    "id": f"REV-{code}-{review_id[:8]}-{index}"[:50],
                    "description": sentence[:500],
                }
            )
    return rules


def process_job(job: dict[str, Any], owner: str) -> str:
    previous: dict[str, Any] = {}
    try:
        _progress(job["id"], owner, 1, STEP_LABELS[1])
        time.sleep(2.5)
        with connection.cursor() as cursor:
            regulations, types, previous = _load_inputs(cursor)
            manual = _manual_rules(cursor)
        # Đọc và kiểm tra văn bản đã đổi so với bản đang áp dụng TRƯỚC khi học: lỗi ký tự, mâu thuẫn giữa các điều.
        from api_core.workflow import regulation_rejection as rejection

        checks = rejection.validate_changes(
            regulations, rejection.changes(regulations, previous["snapshot"]), types
        )
        if any(not c["ok"] for c in checks.values()):
            raise RegulationRejected(checks)
        version = job["target_version"].lstrip("v")
        _progress(job["id"], owner, 2, STEP_LABELS[2])
        time.sleep(2.5)
        compiled = compile_regulations(regulations, types)
        try:
            reviewed = clause_review_cycle(regulations, types)
        except Exception:
            logger.warning("clause_review_cycle_failed", exc_info=True)
            reviewed = []
        seen = {r["id"] for r in manual}
        seen_reviewed = seen | {r["id"] for r in compiled}
        # Văn bản mới thay thế luật tương tự / ngược chiều của văn bản cũ (regulation_precedence): 40 tr -> 50 tr.
        from api_core.workflow import regulation_precedence as precedence

        codes = sorted({r["code"] for r in regulations}, key=len, reverse=True)

        def _tag(rule: dict[str, Any]) -> dict[str, Any]:
            base = rule["id"].removeprefix("REV-")
            code = next((c for c in codes if base.startswith(f"{c}-")), None)
            return {**rule, "source_code": code} if code else rule

        regulation_rules = [_tag(r) for r in compiled if r["id"] not in seen] + [
            _tag(r) for r in reviewed if r["id"] not in seen_reviewed
        ]
        origins = (previous["policy"] or {}).get("origins") or {}
        kept, superseded = precedence.resolve(regulation_rules, origins)
        policy = {
            "version": f"v{version}",
            "rules": manual + kept,
            "origins": precedence.next_origins(
                regulation_rules, origins, version, superseded
            ),
            "superseded": superseded,
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
        time.sleep(2.5)
        # No local fallback: if the engine did not load and enforce the rules,
        # the job must retry/FAIL (old rules stay), never report APPLIED.
        verification = apply_to_ai(policy)
        time.sleep(2.5)
        announcement = build_announcement(
            version=version,
            previous_regulations=previous["snapshot"],
            regulations=snapshot,
            previous_rules=(previous["policy"] or {}).get("rules", []),
            rules=policy["rules"],
            type_names={t.code: t.name for t in types},
        )
        before = {
            (e["old_rule"], e["new_rule"])
            for e in (previous["policy"] or {}).get("superseded") or []
        }
        names = {t.code: t.name for t in types}
        announcement["changes"] = [
            {"kind": "RULE_SUPERSEDED", "title": precedence.describe(e, names)}
            for e in superseded
            if (e["old_rule"], e["new_rule"]) not in before
        ] + list(announcement.get("changes") or [])
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
    except RegulationRejected as exc:
        return _reject(job, owner, exc.checks)
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
