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
import contextlib
import io
import ipaddress
import os
import re
import socket
import threading
import time
import unicodedata
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


def fold_ocr_text(raw_text: str) -> str:
    """Uppercase ASCII form of OCR text for robust matching.

    PaddleOCR's Vietnamese model often drops or garbles diacritics
    ("TỔNG CỘNG" -> "TÓNG CÖNG", "THƯƠNG" -> "THU'O'NG", "DỊCH" -> "Dļch"),
    so field patterns run on this folded text; accented and unaccented inputs
    fold the same.
    """
    raw = (raw_text or "").replace("ļ", "i").replace("Ļ", "I").replace("ı", "i")
    text = unicodedata.normalize("NFD", raw)
    text = text.replace("đ", "d").replace("Đ", "D")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])", "", text)  # U'O'NG -> UONG
    return text.upper()


_COMPANY_TYPE_PREFIX_RE = re.compile(
    r"^(?:(?:TNHH\s+MTV|TNHH|C[OỔÔƠÒÓỎÕỌ]?\.?\s*PH[AẦÂĂÀÁẢÃẠ]?N|CP)\s+)+",
    re.IGNORECASE,
)

# Hậu xử lý các lỗi nhận dạng chữ tiếng Việt phổ biến của PP-OCRv6 trên hóa đơn
_VIETNAMESE_OCR_VENDOR_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bD[ļĻlI1]ch\b", re.IGNORECASE), "Dịch"),
    (re.compile(r"\bDịch\s+V\b", re.IGNORECASE), "Dịch Vụ"),
    (re.compile(r"\bÂu\s+L(?:ac|ạc|c)\b", re.IGNORECASE), "Âu Lạc"),
)


def normalize_vietnamese_ocr_vendor(raw_vendor: str) -> str:
    """Chuẩn hóa tên nhà cung cấp tiếng Việt sau khi trích xuất từ OCR."""
    cleaned = (raw_vendor or "").strip()
    cleaned = re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])", "", cleaned)
    cleaned = _COMPANY_TYPE_PREFIX_RE.sub("", cleaned).strip()
    cleaned = cleaned.replace("ļ", "ị").replace("Ļ", "Ị")
    titled = cleaned.title()
    for pattern, replacement in _VIETNAMESE_OCR_VENDOR_FIXES:
        titled = pattern.sub(replacement, titled)
    return re.sub(r"\s+", " ", titled).strip()


def _first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match
    return None


def parse_invoice_fields(raw_text: str) -> dict:
    """
    Trích xuất các trường phổ biến từ raw OCR text bằng regex + heuristics.
    Hỗ trợ hóa đơn VAT, biên lai, phiếu chi tiêu tiếng Việt, kể cả khi OCR
    làm mất dấu (so khớp trên bản ASCII đã chuẩn hóa).
    """
    text = (raw_text or "").upper()
    folded = fold_ocr_text(raw_text)
    fields = {}

    # --- Số tiền ---
    # Ví dụ: "1.500.000 VND", "1,500,000đ", "150.000 vnđ"
    # Totals come first: a bare "<number> VND" is often a unit price.
    number = r"(\d{1,3}(?:[.,]\d{3})+|\d+)"
    match = _first_match(
        [
            # OCR may drop the vowel entirely: "TỔNG CỘNG" -> "TONG CNG".
            rf"TONG\s*(?:C\w{{0,2}}NG|TIEN)[^\d\n]*{number}",
            rf"THANH\s*TIEN[^\d\n]*{number}",
            rf"AMOUNT[^\d\n]*{number}",
            r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:VND|D\b|\$|USD)",
        ],
        folded,
    )
    if match:
        raw_amount = match.group(1).replace(".", "").replace(",", "")
        if raw_amount.isdigit():
            fields["amount"] = int(raw_amount)

    # --- Ngày ---
    match = _first_match(
        [
            r"NGAY\s+(\d{1,2})\s+THANG\s+(\d{1,2})\s+NAM\s+(\d{4})",
            r"NGAY\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
            r"DATE[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
            r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        ],
        folded,
    )
    if match:
        day, month, year = match.groups()
        fields["invoice_date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # --- Số hóa đơn ---
    match = _first_match(
        [
            r"SO\s*(?:HOA DON|HD|INVOICE)[:\s]+([A-Z0-9\-/]+)",
            r"INVOICE\s*NO[.:\s]+([A-Z0-9\-/]+)",
            r"NO[.:\s]+([A-Z0-9\-/]{5,20})",
        ],
        folded,
    )
    if match:
        fields["invoice_number"] = match.group(1).strip()

    # --- Nhà cung cấp / Công ty ---
    # Prefer the original text (keeps diacritics when OCR read them), then
    # fall back to the folded text when OCR lost the accents.
    vendor = _first_match(
        [
            r"CÔNG\s+TY\s+(?:(?:TNHH\s+MTV|TNHH|C[OỔÔƠÒÓỎÕỌ]?\.?\s*PH[AẦÂĂÀÁẢÃẠ]?N|CP)\s+)?([^\n]{3,80})"
        ],
        text,
    ) or _first_match(
        [
            r"CONG\s+TY\s+(?:(?:TNHH\s+MTV|TNHH|C[O]?\s*PH[A]?N|CP)\s+)?([^\n]{3,80})",
            r"VENDOR[:\s]+([^\n]{3,80})",
            r"SELLER[:\s]+([^\n]{3,80})",
        ],
        folded,
    )
    if vendor:
        fields["vendor_name"] = normalize_vietnamese_ocr_vendor(vendor.group(1))

    # --- MST (Mã số thuế) ---
    mst_match = re.search(r"MST[:\s]+(\d{10,13})", folded)
    if mst_match:
        fields["tax_code"] = mst_match.group(1)

    return fields


# ---------------------------------------------------------------------------
# OCR Engine wrappers
# ---------------------------------------------------------------------------


_ocr_engine = None


_ocr_engine_lock = threading.Lock()


def get_ocr_engine():
    """Lazy Singleton Cache cho PaddleOCR chống rò rỉ bộ nhớ."""
    global _ocr_engine
    if _ocr_engine is None:
        # The startup warm-up thread and the first request must not both
        # build an engine (each load costs seconds and hundreds of MB).
        with _ocr_engine_lock, _model_download_lock():
            if _ocr_engine is None:
                from paddleocr import PaddleOCR

                # PaddleOCR 3.x API (2.x had CVEs, audit S7). Document
                # orientation / unwarping models are skipped: invoices are photos
                # or scans already upright, and each extra model costs memory.
                _ocr_engine = PaddleOCR(
                    lang=settings.ocr_lang,
                    device="gpu" if settings.ocr_use_gpu else "cpu",
                    use_textline_orientation=True,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    # oneDNN in paddlepaddle 3.3 fails on CPU with
                    # "ConvertPirAttribute2RuntimeAttribute not support".
                    enable_mkldnn=False,
                )
    return _ocr_engine


@contextlib.contextmanager
def _model_download_lock():
    """Serialise model download across uvicorn worker processes.

    Each worker warms up at startup; without this two processes download and
    extract the same model archive at once and one fails (FileNotFoundError).
    """
    try:
        import fcntl
    except ImportError:  # Windows dev run: single process, nothing to share
        yield
        return
    lock_dir = os.path.join(os.path.expanduser("~"), ".paddlex")
    os.makedirs(lock_dir, exist_ok=True)
    with open(os.path.join(lock_dir, ".init.lock"), "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def start_ocr_warmup() -> threading.Thread | None:
    """Initialise the OCR engine in a background thread (non-blocking)."""
    if not settings.ocr_warmup:
        return None

    def _warm():
        started = time.perf_counter()
        try:
            get_ocr_engine()
            logger.info(f"OCR engine warmed up in {time.perf_counter() - started:.1f}s")
        except Exception as exc:  # noqa: BLE001 - OCR stays lazy; requests retry
            logger.warning(f"OCR warm-up skipped: {type(exc).__name__}")

    thread = threading.Thread(target=_warm, name="ocr-warmup", daemon=True)
    thread.start()
    return thread


def ocr_with_paddle(image_bytes: bytes) -> tuple[str, float]:
    """Chạy PaddleOCR và trả về (raw_text, confidence)."""
    try:
        import numpy as np
        from PIL import Image

        ocr_engine = get_ocr_engine()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        result = ocr_engine.predict(img_array)
        if not result:
            return "", 0.0
        page = result[0]
        lines = [str(text) for text in page["rec_texts"]]
        confidences = [float(score) for score in page["rec_scores"]]
        if not lines:
            return "", 0.0

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

        genai.configure(api_key=settings.gemini_api_key, transport="rest")
        model = genai.GenerativeModel(settings.gemini_model)

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
            ],
            request_options={"timeout": 20},
        )
        return response.text, 0.75  # Gemini không trả confidence nên hardcode 0.75

    try:
        return await asyncio.to_thread(_call_gemini)
    except Exception as e:
        logger.error(f"Gemini Vision error: {type(e).__name__}: {e}")
        # Library/provider details stay in server logs, never in the response.
        raise HTTPException(
            status_code=502, detail="Không bóc tách được nội dung ảnh."
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
            status_code=400, detail="Không thể phân giải tên miền của URL."
        ) from exc

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        # is_global rejects private, loopback, link-local (cloud metadata),
        # CGNAT 100.64/10, reserved, unspecified and IPv4-mapped variants.
        if not ip.is_global or ip.is_multicast:
            raise HTTPException(
                status_code=400,
                detail=f"Địa chỉ IP mục tiêu {ip_str} thuộc dải mạng bị cấm (SSRF protection).",
            )


MAX_URL_IMAGE_BYTES = 10 * 1024 * 1024


def _check_connected_peer(resp) -> None:
    """Reject the response if the socket is connected to a non-public address."""
    stream = resp.extensions.get("network_stream")
    peer = stream.get_extra_info("server_addr") if stream is not None else None
    if not peer:
        raise HTTPException(status_code=400, detail="Không xác định được máy chủ ảnh.")
    ip = ipaddress.ip_address(peer[0])
    if not ip.is_global or ip.is_multicast:
        raise HTTPException(
            status_code=400,
            detail="Máy chủ ảnh thuộc dải mạng bị cấm (SSRF protection).",
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
        # No redirects (a redirect could point inside the network), size capped
        # while streaming, and the address actually connected to is checked
        # again: DNS may answer differently than during validation (rebinding).
        async with (
            httpx.AsyncClient(timeout=30, follow_redirects=False) as client,
            client.stream("GET", body.image_url) as resp,  # NOSONAR
        ):
            _check_connected_peer(resp)
            resp.raise_for_status()
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_URL_IMAGE_BYTES:
                    raise HTTPException(status_code=413, detail="Ảnh vượt quá 10MB.")
                chunks.append(chunk)
            image_bytes = b"".join(chunks)
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"OCR image download failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=400, detail="Không tải được ảnh từ URL.") from e

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
