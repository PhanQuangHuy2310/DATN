"""
AI Service Client — Dùng trong Django API Core để gọi sang FastAPI AI Service

Usage trong Django views/services:
    from ai_client import ai_client

    # Risk scoring
    result = await ai_client.score_risk(request_data)

    # Auto approve
    decision = await ai_client.evaluate_auto_approve(request_id, ...)

    # Summarize
    summary = await ai_client.summarize_request(title, description, ...)

    # OCR
    ocr_result = await ai_client.extract_from_url(image_url)
"""

try:
    import httpx
except ImportError:
    httpx = None

import asyncio
import os

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("ai_client")

try:
    from django.conf import settings as django_settings

    _URL = getattr(django_settings, "EAS_AI_SERVICE_URL", None)
    _SECRET = getattr(django_settings, "EAS_AI_INTERNAL_SECRET", None)
    _TIMEOUT = getattr(django_settings, "EAS_AI_TIMEOUT_SECONDS", None)
except Exception:  # noqa: BLE001
    _URL, _SECRET, _TIMEOUT = None, None, None

AI_SERVICE_URL = _URL or os.getenv(
    "EAS_AI_SERVICE_URL", os.getenv("AI_SERVICE_URL", "http://localhost:8001")
).rstrip("/")
INTERNAL_SECRET = _SECRET or os.getenv(
    "EAS_AI_INTERNAL_SECRET",
    os.getenv("INTERNAL_API_SECRET", "datn-internal-secret-change-in-prod"),
)
TIMEOUT = float(_TIMEOUT or os.getenv("EAS_AI_TIMEOUT_SECONDS", "30.0"))


def _headers(correlation_id: str | None = None) -> dict:
    headers = {
        "X-Internal-Secret": INTERNAL_SECRET,
        "Content-Type": "application/json",
    }
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    return headers


# ---------------------------------------------------------------------------
# Async client (dùng trong async Django views hoặc Celery async task)
# ---------------------------------------------------------------------------


class AIServiceClient:
    def __init__(self):
        self.base_url = AI_SERVICE_URL
        self.headers = _headers()

    def _get_headers(self, correlation_id: str | None = None) -> dict:
        headers = dict(self.headers)
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    async def health_check(self) -> bool:
        """Kiểm tra AI service còn sống không."""
        if httpx is None:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def score_risk(
        self,
        request_type: str,
        lifecycle_template: str,
        risk_weight: int,
        amount: float = 0.0,
        days_requested: int = 0,
        requester_level: int = 1,
        requester_dept_category: str = "other",
        leave_balance_remaining: int = 0,
        request_count_30d: int = 0,
        reject_count_30d: int = 0,
        attachment_count: int = 0,
        is_near_deadline: bool = False,
        is_weekend_or_holiday: bool = False,
        amount_vs_limit_ratio: float = 0.0,
        amount_vnd: float | None = None,
        num_attachments: int | None = None,
        past_requests_count: int | None = None,
        department: str | None = None,
        has_receipt: int | None = None,
        user_role: str = "junior",
        user_tenure_months: int = 12,
        urgency: str = "medium",
        is_off_hours: int | None = None,
        description_length: int = 150,
        correlation_id: str | None = None,
        **extra_kwargs,
    ) -> dict:
        """
        Gọi AI /risk/score và trả về:
        {
            risk_score: int (1-5),
            risk_label: str,
            confidence: float,
            auto_approve_eligible: bool,
            explanation: dict,
            fallback_used: bool
        }
        Fallback về risk_weight nếu AI service lỗi.
        """
        actual_amount = amount_vnd if amount_vnd is not None else amount
        actual_attachments = (
            num_attachments if num_attachments is not None else attachment_count
        )
        actual_past_requests = (
            past_requests_count
            if past_requests_count is not None
            else request_count_30d
        )
        actual_dept = department if department is not None else requester_dept_category
        actual_receipt = (
            has_receipt
            if has_receipt is not None
            else (1 if actual_attachments > 0 or actual_amount == 0 else 0)
        )
        actual_off_hours = (
            is_off_hours
            if is_off_hours is not None
            else (1 if is_weekend_or_holiday else 0)
        )
        past_rej_rate = min(
            1.0, max(0.0, float(reject_count_30d) / max(1, actual_past_requests))
        )

        payload = {
            "request_type": request_type,
            "lifecycle_template": lifecycle_template,
            "risk_weight": risk_weight,
            "amount_vnd": actual_amount,
            "amount": actual_amount,
            "num_attachments": actual_attachments,
            "attachment_count": actual_attachments,
            "department": actual_dept,
            "requester_dept_category": actual_dept,
            "has_receipt": actual_receipt,
            "past_requests_count": actual_past_requests,
            "request_count_30d": actual_past_requests,
            "past_rejection_rate": past_rej_rate,
            "reject_count_30d": reject_count_30d,
            "is_off_hours": actual_off_hours,
            "is_weekend_or_holiday": bool(actual_off_hours),
            "days_requested": days_requested,
            "requester_level": requester_level,
            "leave_balance_remaining": leave_balance_remaining,
            "is_near_deadline": is_near_deadline,
            "amount_vs_limit_ratio": amount_vs_limit_ratio,
            "user_role": user_role,
            "user_tenure_months": user_tenure_months,
            "urgency": urgency,
            "description_length": description_length,
            **extra_kwargs,
        }

        if httpx is None:
            return {
                "risk_score": risk_weight,
                "risk_label": "unknown",
                "confidence": 0.5,
                "auto_approve_eligible": risk_weight <= 2 and lifecycle_template == "A",
                "explanation": {
                    "error": "httpx_not_installed",
                    "method": "fallback_risk_weight",
                },
                "fallback_used": True,
            }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/ai/risk/score",
                    json=payload,
                    headers=self._get_headers(correlation_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"AI risk/score lỗi, dùng fallback risk_weight={risk_weight}: {e}"
            )
            return {
                "risk_score": risk_weight,
                "risk_label": "unknown",
                "confidence": 0.5,
                "auto_approve_eligible": risk_weight <= 2 and lifecycle_template == "A",
                "explanation": {"error": str(e), "method": "fallback_risk_weight"},
                "fallback_used": True,
            }

    async def evaluate_auto_approve(
        self,
        request_id: str,
        request_type: str,
        lifecycle_template: str,
        risk_score: int,
        requester_name: str,
        requester_dept: str,
        amount: float = 0.0,
        days_requested: int = 0,
        leave_balance_remaining: int = 0,
        room_available: bool | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """
        Gọi AI /auto-approve/evaluate và trả về:
        {
            decision: "auto_approve" | "escalate_to_human",
            reason: str,
            detail_reasons: list[str],
            auto_approve_note: str | None,
            evaluated_at: str
        }
        """
        if httpx is None:
            return {
                "decision": "escalate_to_human",
                "reason": "AI Client chưa cài đặt httpx",
                "detail_reasons": [
                    "❌ Thư viện HTTP chưa sẵn sàng — chuyển người duyệt thủ công"
                ],
                "auto_approve_note": None,
                "evaluated_at": "",
            }

        payload = {
            "request_id": request_id,
            "request_type": request_type,
            "lifecycle_template": lifecycle_template,
            "risk_score": risk_score,
            "requester_name": requester_name,
            "requester_dept": requester_dept,
            "amount": amount,
            "days_requested": days_requested,
            "leave_balance_remaining": leave_balance_remaining,
            "room_available": room_available,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/ai/auto-approve/evaluate",
                    json=payload,
                    headers=self._get_headers(correlation_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AI auto-approve lỗi, escalate thủ công: {e}")
            return {
                "decision": "escalate_to_human",
                "reason": f"AI Service không khả dụng: {e}",
                "detail_reasons": [
                    "❌ AI Service không phản hồi — chuyển người duyệt thủ công"
                ],
                "auto_approve_note": None,
                "evaluated_at": "",
            }

    async def summarize_request(
        self,
        title: str,
        request_type: str,
        requester_name: str,
        description: str | None = None,
        data: dict | None = None,
        risk_score: int | None = None,
        amount: float | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """
        Gọi AI /summarize/request và trả về:
        {
            summary: str,
            key_points: list[str],
            sentiment: str,
            tokens_used: int
        }
        Fallback về title nếu lỗi.
        """
        payload = {
            "title": title,
            "description": description,
            "request_type": request_type,
            "requester_name": requester_name,
            "data": data,
            "risk_score": risk_score,
            "amount": amount,
        }

        if httpx is None:
            return {
                "summary": title,
                "key_points": [],
                "sentiment": "normal",
                "tokens_used": 0,
            }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/ai/summarize/request",
                    json=payload,
                    headers=self._get_headers(correlation_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AI summarize lỗi: {e}")
            return {
                "summary": title,
                "key_points": [],
                "sentiment": "normal",
                "tokens_used": 0,
            }

    async def extract_ocr_from_url(
        self,
        image_url: str,
        request_type: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """
        Gọi AI /ocr/extract-url và trả về:
        {
            raw_text: str,
            extracted_fields: dict,
            confidence: float,
            engine: str
        }
        """
        if httpx is None:
            return {
                "raw_text": "",
                "extracted_fields": {},
                "confidence": 0.0,
                "engine": "error",
            }

        payload = {"image_url": image_url, "request_type": request_type}

        try:
            async with httpx.AsyncClient(
                timeout=60.0
            ) as client:  # OCR cần thêm thời gian
                resp = await client.post(
                    f"{self.base_url}/ai/ocr/extract-url",
                    json=payload,
                    headers=self._get_headers(correlation_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AI OCR lỗi: {e}")
            return {
                "raw_text": "",
                "extracted_fields": {},
                "confidence": 0.0,
                "engine": "error",
            }

    async def classify_request(
        self,
        title: str,
        description: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        """
        Gọi AI /classify/request và trả về:
        {
            predicted_request_type: str,
            predicted_department: str,
            predicted_template: str,
            confidence_request_type: float,
            confidence_department: float,
            confidence_template: float,
            workflow_suggestion: str
        }
        """
        if httpx is None:
            return {
                "predicted_request_type": "leave_annual",
                "predicted_department": "hr",
                "predicted_template": "A",
                "confidence_request_type": 0.5,
                "confidence_department": 0.5,
                "confidence_template": 0.5,
                "workflow_suggestion": "Fallback mặc định: httpx not installed",
                "fallback_used": True,
            }

        payload = {"title": title, "description": description}

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/ai/classify/request",
                    json=payload,
                    headers=self._get_headers(correlation_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"AI classify lỗi: {e}")
            return {
                "predicted_request_type": "leave_annual",
                "predicted_department": "hr",
                "predicted_template": "A",
                "confidence_request_type": 0.5,
                "confidence_department": 0.5,
                "confidence_template": 0.5,
                "workflow_suggestion": f"Fallback mặc định: {e}",
                "fallback_used": True,
            }


# ---------------------------------------------------------------------------
# Sync wrapper (dùng trong Django sync views nếu cần)
# ---------------------------------------------------------------------------


class SyncAIServiceClient:
    """Wrapper đồng bộ cho AIServiceClient, dùng trong Django sync contexts."""

    def __init__(self):
        self._async_client = AIServiceClient()

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Trong context async (Celery, ASGI) — dùng asyncio.ensure_future
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=35)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def classify_request(
        self,
        title: str,
        description: str = "",
        correlation_id: str | None = None,
    ) -> dict:
        return self._run(
            self._async_client.classify_request(
                title, description, correlation_id=correlation_id
            )
        )

    def score_risk(self, **kwargs) -> dict:
        return self._run(self._async_client.score_risk(**kwargs))

    def evaluate_auto_approve(self, **kwargs) -> dict:
        return self._run(self._async_client.evaluate_auto_approve(**kwargs))

    def summarize_request(self, **kwargs) -> dict:
        return self._run(self._async_client.summarize_request(**kwargs))

    def extract_ocr_from_url(
        self,
        image_url: str,
        request_type: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        return self._run(
            self._async_client.extract_ocr_from_url(
                image_url, request_type, correlation_id=correlation_id
            )
        )


# Singleton instances để import
ai_client = AIServiceClient()
ai_client_sync = SyncAIServiceClient()
