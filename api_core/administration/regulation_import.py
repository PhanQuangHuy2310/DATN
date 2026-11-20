"""Nhập văn bản quy định viết sẵn (.txt / .md / .docx) vào biểu mẫu ban hành.

Chỉ trích chữ, không lưu file: kết quả đổ vào ô nội dung để admin xem, AI kiểm tra rồi mới ban hành.
Loại file xác định bằng magic bytes (ZIP có word/document.xml, hoặc văn bản UTF-8/UTF-16), không theo đuôi tên.
"""

from __future__ import annotations

import base64
import binascii
import html
import io
import re
import zipfile
from typing import Any

from django.http import HttpRequest, JsonResponse

from api_core.authn.service import require_actor
from api_core.http import JsonBodyError, api_error, parse_json_object

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DOCX_XML_BYTES = 8 * 1024 * 1024  # chặn zip bomb: document.xml giải nén tối đa 8 MB
MAX_TEXT_CHARS = 20000

_PARAGRAPH = re.compile(r"<w:p[ >].*?</w:p>|<w:p/>", re.DOTALL)
_RUN_TOKEN = re.compile(
    r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|<w:tab/>|<w:br/>|<w:cr/>", re.DOTALL
)
_ARTICLE = re.compile(r"^\s*(?:Điều|Dieu|Article)\s+\d+", re.IGNORECASE)
_META = re.compile(
    r"^\s*(Mã quy định|Mã|Danh mục|Nhóm|Tiêu đề)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE
)
_MD_PREFIX = re.compile(r"^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|>\s+)")
_CODE_OK = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,29}$")


class ImportError_(ValueError):
    """Lỗi người dùng sửa được (mã lỗi trả về client)."""


def _docx_text(data: bytes) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportError_("FILE_TYPE_NOT_ALLOWED") from exc
    with archive:
        try:
            info = archive.getinfo("word/document.xml")
        except KeyError as exc:  # ZIP nhưng không phải Word (xlsx, zip thường...)
            raise ImportError_("FILE_TYPE_NOT_ALLOWED") from exc
        if info.file_size > MAX_DOCX_XML_BYTES:
            raise ImportError_("FILE_TOO_LARGE")
        with archive.open(info) as handle:
            xml = handle.read(MAX_DOCX_XML_BYTES + 1)
    if len(xml) > MAX_DOCX_XML_BYTES:
        raise ImportError_("FILE_TOO_LARGE")
    text = xml.decode("utf-8", errors="replace")
    # Không dựng cây XML (tránh entity expansion): chỉ quét thẻ đoạn và thẻ chữ của Word.
    lines = []
    for paragraph in _PARAGRAPH.findall(text):
        parts = []
        for match in _RUN_TOKEN.finditer(paragraph):
            token = match.group(0)
            if match.group(1) is not None:
                parts.append(html.unescape(match.group(1)))
            elif token == "<w:tab/>":
                parts.append(" ")
            else:
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def _plain_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise ImportError_("FILE_TYPE_NOT_ALLOWED") from exc
    if b"\x00" in data:  # nhị phân (ảnh, pdf, exe...) chứ không phải văn bản
        raise ImportError_("FILE_TYPE_NOT_ALLOWED")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportError_("TEXT_NOT_UTF8") from exc


def extract_regulation(data: bytes) -> dict[str, Any]:
    """bytes -> {title, code, category, content, source, articles}. Không ghi gì ra đĩa."""
    if not data:
        raise ImportError_("FILE_EMPTY")
    if len(data) > MAX_FILE_BYTES:
        raise ImportError_("FILE_TOO_LARGE")
    if data.startswith(b"PK\x03\x04"):
        raw, source = _docx_text(data), "docx"
    elif data.startswith((b"%PDF", b"\xd0\xcf\x11\xe0")):  # PDF, Word 97 (.doc)
        raise ImportError_("FILE_TYPE_NOT_ALLOWED")
    else:
        raw, source = _plain_text(data), "text"

    meta: dict[str, str] = {}
    body: list[str] = []
    title = ""
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _MD_PREFIX.sub("", line).replace("**", "").strip()
        if not line:
            continue
        found = _META.match(line)
        if found and not body:
            meta[found.group(1).lower()] = found.group(2)
            continue
        # Dòng đầu không phải "Điều N" là tiêu đề văn bản (vd "QUY ĐỊNH VỀ NGHỈ PHÉP").
        if (
            not title
            and not body
            and not _ARTICLE.match(line)
            and "tiêu đề" not in meta
        ):
            title = line
            continue
        body.append(line)

    content = "\n".join(body)
    if not content.strip():
        raise ImportError_("NO_CONTENT")
    if len(content) > MAX_TEXT_CHARS:
        raise ImportError_("CONTENT_TOO_LONG")
    code = (meta.get("mã quy định") or meta.get("mã") or "").strip().upper()
    return {
        "title": (meta.get("tiêu đề") or title)[:300],
        "code": code if _CODE_OK.match(code) else "",
        "category": (meta.get("danh mục") or meta.get("nhóm") or "")[:120],
        "content": content,
        "source": source,
        "articles": sum(1 for line in body if _ARTICLE.match(line)),
    }


_MESSAGES = {
    "FILE_EMPTY": "File rỗng.",
    "FILE_TOO_LARGE": "File quá lớn (tối đa 2 MB).",
    "FILE_TYPE_NOT_ALLOWED": "Chỉ nhận file văn bản .txt / .md hoặc Word .docx (PDF, .doc cũ chưa hỗ trợ).",
    "TEXT_NOT_UTF8": "File văn bản không phải UTF-8. Lưu lại file với mã hóa UTF-8 rồi thử lại.",
    "NO_CONTENT": "Không tìm thấy nội dung điều khoản trong file.",
    "CONTENT_TOO_LONG": "Nội dung dài quá 20000 ký tự; tách thành nhiều quy định.",
}


@require_actor("OPS_ADMIN", "POLICY_ADMIN")
def regulation_import_view(request: HttpRequest) -> JsonResponse:
    """POST /api/v1/admin/regulations/import {filename, data_base64} -> văn bản đã trích (không lưu)."""
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    try:
        body = parse_json_object(request, max_bytes=(MAX_FILE_BYTES * 4) // 3 + 4096)
    except JsonBodyError as exc:
        code = "FILE_TOO_LARGE" if str(exc) == "BODY_TOO_LARGE" else str(exc)
        return api_error(request, code, status=400)
    try:
        data = base64.b64decode(str(body.get("data_base64") or ""), validate=True)
    except (binascii.Error, ValueError):
        return api_error(request, "MALFORMED_FILE", status=400)
    try:
        result = extract_regulation(data)
    except ImportError_ as exc:
        code = str(exc)
        return api_error(
            request, code, status=422, fields={"file": [_MESSAGES.get(code, code)]}
        )
    return JsonResponse({"imported": result})
