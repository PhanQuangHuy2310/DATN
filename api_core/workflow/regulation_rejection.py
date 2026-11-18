"""Trả lại quy định lỗi: hiệu lực quay về bản AI đã áp dụng gần nhất, bản lỗi được giữ kèm danh sách lỗi (migration 26).

Dùng trong lượt học của AI (workflow/ai_learning.py):
  - văn bản thay đổi có lỗi chặn (regulation_validation: lỗi ký tự, mâu thuẫn giữa các điều)  -> cause VALIDATION;
  - AI học thất bại sau mọi lần thử (lỗi kỹ thuật)                                            -> cause TECHNICAL.
Khi đó mọi quy định đã đổi so với bản đã áp dụng (eas.ai_system_state.applied_snapshot) được đưa về đúng nội dung
đã áp dụng: thêm mới thì gỡ, sửa thì trả nội dung cũ, bãi bỏ thì khôi phục. Mỗi thao tác có phiên bản mới trong lịch sử
ghi rõ "trả lại". Bản bị trả lại nằm ở eas.regulation_rejection (OPEN) cho tới khi admin nạp lại mã đó (RESOLVED) hoặc
bỏ qua (DISMISSED).
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.types.json import Jsonb

from api_core.workflow.regulation_compiler import RequestTypeName
from api_core.workflow.regulation_validation import validate

logger = logging.getLogger(__name__)
RESTORED_BY = "AI (trả lại, khôi phục bản đã áp dụng)"


def available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('eas.regulation_rejection') IS NOT NULL")
    return bool(cursor.fetchone()[0])


def changes(regulations: list[dict[str, Any]], snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Quy định đã đổi so với bản AI đã áp dụng: [{code, action, current, applied}]."""
    applied = {s["code"]: s for s in snapshot or []}
    current = {r["code"]: r for r in regulations}
    out = []
    for code, reg in current.items():
        old = applied.get(code)
        if old is None:
            out.append({"code": code, "action": "CREATE", "current": reg, "applied": None})
        elif (reg.get("title"), reg.get("content")) != (old.get("title"), old.get("content")):
            out.append({"code": code, "action": "UPDATE", "current": reg, "applied": old})
    for code, old in applied.items():
        if code not in current:
            out.append({"code": code, "action": "DELETE", "current": None, "applied": old})
    return sorted(out, key=lambda c: c["code"])


def validate_changes(
    regulations: list[dict[str, Any]], changed: list[dict[str, Any]], types: list[RequestTypeName]
) -> dict[str, dict[str, Any]]:
    """Kiểm tra từng văn bản thêm/sửa so với các quy định khác đang có; {code: kết quả validate}."""
    out = {}
    for change in changed:
        reg = change["current"]
        if reg is None:
            continue
        others = [r for r in regulations if r["code"] != reg["code"]]
        out[reg["code"]] = validate(code=reg["code"], title=reg.get("title") or "", content=reg.get("content") or "",
                                    types=types, others=others)
    return out


def _snapshot(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        "SELECT code, title, content, version_string FROM eas.company_regulations WHERE NOT is_deleted ORDER BY code"
    )
    return [{"code": r[0], "title": r[1], "content": r[2] or "", "version": r[3]} for r in cursor.fetchall()]


def _label_history(cursor, regulation_id: str, summary: str) -> None:
    cursor.execute(
        """
        UPDATE eas.regulation_versions SET change_summary = %s
        WHERE id = (SELECT id FROM eas.regulation_versions WHERE regulation_id = %s ORDER BY created_at DESC LIMIT 1)
        """,
        [summary[:500], regulation_id],
    )


def rollback_to_applied(
    cursor,
    *,
    job_id: str | None,
    cause: str,
    message: str,
    validation: dict[str, dict[str, Any]] | None = None,
    only_codes: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Đưa văn bản về bản đã áp dụng và lưu các bản bị trả lại; [] nếu chưa có migration 26 hoặc chưa từng áp dụng."""
    if not available(cursor):
        return []
    cursor.execute("SELECT applied_snapshot FROM eas.ai_system_state WHERE id = 1")
    row = cursor.fetchone()
    snapshot = (row[0] if row else None) or []
    if not isinstance(snapshot, list) or not snapshot:
        return []
    cursor.execute(
        "SELECT code, title, category, content, version_string FROM eas.company_regulations WHERE NOT is_deleted"
    )
    regulations = [{"code": r[0], "title": r[1], "category": r[2], "content": r[3] or "", "version": r[4]}
                   for r in cursor.fetchall()]
    changed = [c for c in changes(regulations, snapshot) if only_codes is None or c["code"] in only_codes]
    if not changed:
        return []
    validation = validation or {}
    rejected = []
    for change in changed:
        code, action, cur, old = change["code"], change["action"], change["current"], change["applied"]
        result = validation.get(code) or {}
        errors = list(result.get("errors") or [])
        if cause == "TECHNICAL" or not errors:
            errors = errors or [{"severity": "ERROR", "kind": cause, "message": message[:1000]}]
        restored_version = None
        if action == "CREATE":
            cursor.execute(
                "UPDATE eas.company_regulations SET is_deleted = true, updated_by = %s "
                "WHERE code = %s AND NOT is_deleted RETURNING id::text, version_string",
                [RESTORED_BY, code],
            )
            rid, restored_version = cursor.fetchone()
            _label_history(cursor, rid, f"Trả lại quy định mới {code} (bản {cur['version']} có lỗi), gỡ khỏi hiệu lực")
        elif action == "UPDATE":
            cursor.execute(
                "UPDATE eas.company_regulations SET title = %s, content = %s, updated_by = %s "
                "WHERE code = %s AND NOT is_deleted RETURNING id::text, version_string",
                [old["title"], old["content"], RESTORED_BY, code],
            )
            rid, restored_version = cursor.fetchone()
            _label_history(cursor, rid, f"Trả lại bản {cur['version']} của {code} (có lỗi), khôi phục nội dung "
                                        f"bản {old.get('version')}")
        else:  # bãi bỏ bị trả lại: khôi phục bản cũ đã bị gỡ
            cursor.execute(
                """
                UPDATE eas.company_regulations SET is_deleted = false, title = %s, content = %s, updated_by = %s
                WHERE id = (SELECT id FROM eas.company_regulations WHERE code = %s AND is_deleted
                            ORDER BY updated_at DESC LIMIT 1)
                RETURNING id::text, version_string
                """,
                [old["title"], old["content"], RESTORED_BY, code],
            )
            row = cursor.fetchone()
            restored_version = row[1] if row else None
        cursor.execute(
            """
            INSERT INTO eas.regulation_rejection(job_id, regulation_code, action, cause, rejected_title,
                                                 rejected_content, rejected_version, restored_version, errors,
                                                 warnings, message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            [job_id, code, action, cause, (cur or old or {}).get("title"), (cur or {}).get("content"),
             (cur or {}).get("version"), restored_version, Jsonb(errors),
             Jsonb(list(result.get("warnings") or [])), message[:4000]],
        )
        rejected.append({"id": cursor.fetchone()[0], "code": code, "action": action,
                         "rejected_version": (cur or {}).get("version"), "restored_version": restored_version,
                         "errors": errors[:10]})
    # Các mã đã khôi phục giờ trùng nội dung với bộ luật đang áp dụng, chỉ khác số phiên bản: cập nhật ảnh chụp để lượt
    # sau so đúng. Nếu không còn thay đổi nào khác đang chờ học, phiên bản hiệu lực = phiên bản mới nhất.
    restored = {r["code"]: r["restored_version"] for r in rejected if r["restored_version"]}
    new_snapshot = [{**s, "version": restored.get(s["code"], s.get("version"))} for s in snapshot]
    pending = changes(_snapshot(cursor), new_snapshot)
    cursor.execute(
        """
        UPDATE eas.ai_system_state
        SET applied_snapshot = %s,
            active_regulation_version = CASE WHEN %s THEN target_regulation_version ELSE active_regulation_version END,
            updated_at = now()
        WHERE id = 1
        """,
        [Jsonb(new_snapshot), not pending],
    )
    try:
        from api_core.read_cache import invalidate

        invalidate()
    except Exception:
        logger.debug("regulation cache invalidation skipped", exc_info=True)
    return rejected


ACTION_TEXT = {"CREATE": "thêm mới", "UPDATE": "sửa", "DELETE": "bãi bỏ"}


def announcement_text(
    rejected: list[dict[str, Any]], cause: str, message: str
) -> tuple[str, str, list[dict[str, str]], list[dict[str, Any]]]:
    """Tiêu đề, tóm tắt, danh sách lỗi (mục "Thay đổi" của hộp thông báo) và hướng dẫn xử lý cho admin."""
    codes = ", ".join(r["code"] for r in rejected)
    changes: list[dict[str, str]] = []
    for r in rejected:
        head = f"{r['code']} ({ACTION_TEXT.get(r['action'], r['action'])}, bản {r.get('rejected_version') or '?'})"
        for e in (r.get("errors") or [])[:3]:
            where = f"{e['article']}: " if e.get("article") else ""
            changes.append({"kind": "REGULATION_REJECTED", "title": f"{head}: {where}{e['message'].rstrip('. ')}"})
    guidance = [{
        "title": "Cách xử lý",
        "steps": [
            "Vào Quy định, mục \u201cQuy định bị trả lại\u201d ở đầu trang.",
            "Đọc từng lỗi AI chỉ ra (câu, điều khoản bị chồng), bấm \u201cSửa và nạp lại\u201d.",
            "Sửa đúng các chỗ đó, bấm \u201cAI kiểm tra trước\u201d tới khi không còn lỗi, rồi ban hành lại.",
        ],
    }]
    if cause == "VALIDATION":
        title = f"Quy định {codes} bị trả lại: văn bản có lỗi"
        summary = ("AI kiểm tra văn bản và phát hiện lỗi nên KHÔNG áp dụng. Hiệu lực đã quay về bản đã áp dụng "
                   "trước đó (văn bản và bộ luật AI). Các lỗi được liệt kê bên dưới.")
    else:
        title = f"Quy định {codes} bị trả lại: AI chưa học được"
        summary = (f"Sau mọi lần thử, AI chưa áp dụng được quy định mới (lỗi kỹ thuật: {message[:300].rstrip('. ')}). "
                   "Hiệu lực đã quay về bản đã áp dụng trước đó. Nội dung bản bị trả lại vẫn được giữ để nạp lại "
                   "khi AI service hoạt động.")
        guidance[0]["steps"][1] = "Kiểm tra AI service đã chạy, rồi bấm \u201cSửa và nạp lại\u201d (nội dung giữ nguyên)."
    return title[:300], summary[:4000], changes, guidance


def resolve_open(cursor, *, code: str, actor_id: str, note: str) -> int:
    """Admin nạp lại một mã quy định: các bản bị trả lại đang mở của mã đó coi như đã xử lý."""
    if not available(cursor):
        return 0
    cursor.execute(
        """
        UPDATE eas.regulation_rejection
        SET state = 'RESOLVED', resolved_by = %s, resolved_at = statement_timestamp(), note = %s
        WHERE regulation_code = %s AND state = 'OPEN'
        """,
        [actor_id, note[:500], code],
    )
    return cursor.rowcount
