"""
Router: OCR — Bóc tách thông tin từ hóa đơn / chứng từ đính kèm

POST /ai/ocr/extract
  - Input: file ảnh (JPEG/PNG/PDF) hoặc URL ảnh
  - Output: JSON với các trường bóc tách được (số hóa đơn, số tiền, ngày, nhà cung cấp...)

Dùng PaddleOCR (pre-trained tiếng Việt) — không cần train thêm.
Fallback: nếu PaddleOCR chưa cài được thì trả về raw text từ Gemini Vision.
"""

import asyncio
import base64
import io
import ipaddress
import re
import socket
from urllib.parse import urlparse

try:
    from config import get_settings
except (ImportError, AttributeError):
    from ai_service.config import get_settings

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel

MIME_JPEG = "image/jpeg"
settings = get_settings()
router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class OCRResult(BaseModel):
    raw_text: str
    extracted_fields: dict
    confidence: float
    engine: str  # "paddleocr" hoặc "gemini-vision"


class OCRUrlRequest(BaseModel):
    image_url: str
    request_type: str | None = None  # Gợi ý cho engine biết loại chứng từ


# ---------------------------------------------------------------------------
# Helper: post-process raw text → structured fields
# ---------------------------------------------------------------------------


def parse_invoice_fields(raw_text: str) -> dict:
    """
    Trích xuất các trường phổ biến từ raw OCR text bằng regex + heuristics.
    Hỗ trợ hóa đơn VAT, biên lai, phiếu chi tiêu tiếng Việt.
    """
    text = raw_text.upper()
    fields = {}

    # --- Số tiền ---
    # Ví dụ: "1.500.000 VND", "1,500,000đ", "150.000 vnđ"
    amount_patterns = [
        r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:VN[DĐ]|Đ|VNĐ|\$|USD)",
        r"TỔNG\s*(?:CỘNG|TIỀN)[^:]*:\s*([\d.,]+)",
        r"THÀNH\s*TIỀN[^:]*:\s*([\d.,]+)",
        r"AMOUNT[^:]*:\s*([\d.,]+)",
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            raw_amount = match.group(1).replace(".", "").replace(",", "")
            try:
                fields["amount"] = int(raw_amount)
                break
            except ValueError:
                continue

    # --- Ngày ---
    date_patterns = [
        r"NGÀY\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        r"DATE[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                fields["invoice_date"] = (
                    f"{groups[2]}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
                )
                break

    # --- Số hóa đơn ---
    invoice_no_patterns = [
        r"SỐ\s*(?:HÓA ĐƠN|HD|INVOICE)[:\s]+([A-Z0-9\-/]+)",
        r"INVOICE\s*NO[.:\s]+([A-Z0-9\-/]+)",
        r"NO[.:\s]+([A-Z0-9\-/]{5,20})",
    ]
    for pattern in invoice_no_patterns:
        match = re.search(pattern, text)
        if match:
            fields["invoice_number"] = match.group(1).strip()
            break

    # --- Nhà cung cấp / Công ty ---
    vendor_patterns = [
        r"CÔNG TY\s+(?:TNHH|CỔ PHẦN|CP|TNHH MTV)?\s*([A-Z\s]{5,40})",
        r"VENDOR[:\s]+([A-Z\s]{5,40})",
        r"SELLER[:\s]+([A-Z\s]{5,40})",
    ]
    for pattern in vendor_patterns:
        match = re.search(pattern, text)
        if match:
            fields["vendor_name"] = match.group(1).strip().title()
            break

    # --- MST (Mã số thuế) ---
    mst_match = re.search(r"MST[:\s]+(\d{10,13})", text)
    if mst_match:
        fields["tax_code"] = mst_match.group(1)

    return fields


# ---------------------------------------------------------------------------
# OCR Engine wrappers
# ---------------------------------------------------------------------------


_ocr_engine = None


def get_ocr_engine():
    """Lazy Singleton Cache cho PaddleOCR chống rò rỉ bộ nhớ."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(
            use_angle_cls=True, lang=settings.ocr_lang, use_gpu=settings.ocr_use_gpu
        )
    return _ocr_engine


def ocr_with_paddle(image_bytes: bytes) -> tuple[str, float]:
    """Chạy PaddleOCR và trả về (raw_text, confidence)."""
    try:
        import numpy as np
        from PIL import Image

        ocr_engine = get_ocr_engine()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        result = ocr_engine.ocr(img_array, cls=True)
        if not result or not result[0]:
            return "", 0.0

        lines = []
        confidences = []
        for line in result[0]:
            text = line[1][0]
            conf = line[1][1]
            lines.append(text)
            confidences.append(conf)

        raw_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return raw_text, round(avg_conf, 4)

    except ImportError:
        logger.warning("PaddleOCR chưa cài. Dùng fallback Gemini Vision.")
        raise


async def ocr_with_gemini_vision(
    image_bytes: bytes, mime_type: str = MIME_JPEG
) -> tuple[str, float]:
    """Dùng Gemini Vision làm fallback khi PaddleOCR chưa khả dụng."""

    def _call_gemini() -> tuple[str, float]:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        b64 = base64.b64encode(image_bytes).decode()
        prompt = (
            "Hãy đọc toàn bộ nội dung trong ảnh này theo đúng thứ tự từ trên xuống dưới, "
            "trả về text thuần (không format markdown). "
            "Giữ nguyên số tiền, ngày tháng và các mã số."
        )
        response = model.generate_content(
            [
                {"mime_type": mime_type, "data": b64},
                prompt,
            ]
        )
        return response.text, 0.75  # Gemini không trả confidence nên hardcode 0.75

    try:
        return await asyncio.to_thread(_call_gemini)
    except Exception as e:
        logger.error(f"Gemini Vision error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Cả PaddleOCR và Gemini Vision đều lỗi: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/extract", response_model=OCRResult, summary="Bóc tách từ file upload")
async def extract_from_upload(
    file: UploadFile = File(..., description="Ảnh hóa đơn/chứng từ (JPEG, PNG)"),  # noqa: B008
    request_type: str | None = Form(
        None, description="Loại yêu cầu để gợi ý trường bóc tách"
    ),
):
    """
    Upload ảnh hóa đơn → trả về JSON gồm raw text và các trường đã bóc tách.

    - **file**: ảnh JPEG hoặc PNG
    - **request_type**: ví dụ `"purchase"`, `"expense_claim"` (tùy chọn)
    """
    allowed_types = {MIME_JPEG, "image/png", "image/webp", "image/tiff"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ hỗ trợ JPEG/PNG/WebP/TIFF. Nhận được: {file.content_type}",
        )

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="File quá lớn. Tối đa 10MB.")

    # Thử PaddleOCR trước, fallback sang Gemini Vision
    engine = "paddleocr"
    try:
        raw_text, confidence = ocr_with_paddle(image_bytes)
    except Exception:  # noqa: BLE001
        engine = "gemini-vision"
        raw_text, confidence = await ocr_with_gemini_vision(
            image_bytes, file.content_type
        )

    extracted = parse_invoice_fields(raw_text)
    logger.info(
        f"OCR [{engine}] → {len(raw_text)} chars, conf={confidence}, fields={list(extracted.keys())}"
    )

    return OCRResult(
        raw_text=raw_text,
        extracted_fields=extracted,
        confidence=confidence,
        engine=engine,
    )


def validate_safe_image_url(url: str) -> None:
    """Kiểm tra URL chống SSRF: chỉ cho phép http/https, chặn private/loopback/metadata IP."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"Scheme '{parsed.scheme}' không được hỗ trợ. Chỉ cho phép http và https.",
        )
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="URL không hợp lệ: thiếu hostname.")

    lowered_host = hostname.lower()
    if lowered_host in ("metadata.google.internal", "metadata", "instance-data"):
        raise HTTPException(
            status_code=400,
            detail="Truy cập hostname nội bộ bị cấm (SSRF protection).",
        )

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400, detail=f"Không thể phân giải tên miền {hostname}: {exc}"
        ) from exc

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or (ip.version == 4 and ip_str.startswith("169.254."))
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Địa chỉ IP mục tiêu {ip_str} thuộc dải mạng bị cấm (SSRF protection).",
            )


@router.post("/extract-url", response_model=OCRResult, summary="Bóc tách từ URL ảnh")
async def extract_from_url(body: OCRUrlRequest):
    """
    Nhận URL ảnh → download → chạy OCR → trả kết quả.
    Dùng khi ảnh đã được upload lên Supabase Storage.
    """
    validate_safe_image_url(body.image_url)

    import httpx

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(body.image_url)  # NOSONAR
            resp.raise_for_status()

            image_bytes = resp.content
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Không tải được ảnh từ URL: {e}")

    engine = "paddleocr"
    try:
        raw_text, confidence = ocr_with_paddle(image_bytes)
    except Exception:  # noqa: BLE001
        engine = "gemini-vision"
        raw_text, confidence = await ocr_with_gemini_vision(image_bytes, content_type)

    extracted = parse_invoice_fields(raw_text)
    return OCRResult(
        raw_text=raw_text,
        extracted_fields=extracted,
        confidence=confidence,
        engine=engine,
    )
