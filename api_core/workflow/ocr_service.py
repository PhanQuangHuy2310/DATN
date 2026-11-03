"""OCR of a stored attachment, recorded on the request's audit chain (C4).

The file is read with the same authorization as a download and sent only to
the internal AI service. Results are suggestions for the human: they never
change the form or the decision by themselves. If no OCR engine can run, the
caller gets OCR_UNAVAILABLE instead of an invented result.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.db import connection, transaction

from api_core.ai_client import OcrUnavailableError
from api_core.authn.models import Actor
from api_core.workflow.attachments import download_attachment
from api_core.workflow.service import (
    SQL_LOCK_SECURITY,
    CommandError,
    _append_request_audit,
)

OCR_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/tiff"})
OCR_ACTION = "AI_OCR_RECORDED"
# Only structured fields are kept; the raw text may contain personal data.
KEPT_FIELDS = (
    "invoice_number",
    "tax_code",
    "invoice_date",
    "amount",
    "vendor_name",
)


def run_attachment_ocr(actor: Actor, attachment_id: str, cid: str) -> dict[str, Any]:
    from api_core.integrations.ai_service import ai_client_sync

    data, filename, mime = download_attachment(
        actor=actor, attachment_id=attachment_id, correlation_id=cid
    )
    if mime not in OCR_MIME_TYPES:
        raise CommandError("OCR_UNSUPPORTED_TYPE", status=422)
    try:
        result = ai_client_sync.extract_ocr_from_bytes(
            data, filename, mime, correlation_id=cid
        )
    except OcrUnavailableError as exc:
        raise CommandError("OCR_UNAVAILABLE", status=503) from exc
    extracted = result.get("extracted_fields") or {}
    confidence = result.get("confidence")
    record = {
        "attachment_id": attachment_id,
        "engine": str(result.get("engine") or "unknown"),
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        "extracted_fields": {k: extracted[k] for k in KEPT_FIELDS if k in extracted},
        "text_length": len(result.get("raw_text") or ""),
    }
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(SQL_LOCK_SECURITY)
        cursor.execute(
            "SELECT request_id::text FROM eas.attachment WHERE id = %s", [attachment_id]
        )
        request_id = cursor.fetchone()[0]
        _append_request_audit(
            cursor,
            request_id=request_id,
            actor_id=actor.id,
            action=OCR_ACTION,
            target_type="attachment",
            target_id=attachment_id,
            details=record,
            correlation_id=cid or str(uuid4()),
        )
    return {"ocr": record}
