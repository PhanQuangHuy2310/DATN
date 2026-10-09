from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    version: str


def sniff_allowed_mime(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise StorageError("FILE_TYPE_NOT_ALLOWED")


def scan_with_clamav(data: bytes) -> None:
    try:
        with socket.create_connection(
            (settings.EAS_CLAMAV_HOST, settings.EAS_CLAMAV_PORT), timeout=10
        ) as scanner:
            scanner.settimeout(30)
            scanner.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 64 * 1024):
                chunk = data[offset : offset + 64 * 1024]
                scanner.sendall(struct.pack("!I", len(chunk)) + chunk)
            scanner.sendall(struct.pack("!I", 0))
            response = scanner.recv(4096).decode("utf-8", errors="replace")
    except (TimeoutError, OSError) as exc:
        raise StorageError("MALWARE_SCANNER_UNAVAILABLE") from exc
    if not response.endswith("OK\0"):
        if "FOUND" in response:
            raise StorageError("MALWARE_DETECTED")
        raise StorageError("MALWARE_SCAN_FAILED")


def _object_url(key: str) -> str:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
        raise StorageError("STORAGE_NOT_CONFIGURED")
    bucket = quote(settings.EAS_STORAGE_BUCKET, safe="")
    object_key = quote(key, safe="/")
    return f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{object_key}"


def _headers(mime: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
        "apikey": settings.SUPABASE_SECRET_KEY,
    }
    if mime:
        headers.update(
            {"Content-Type": mime, "x-upsert": "false", "Cache-Control": "no-store"}
        )
    return headers


def put_private_object(
    *, key: str, data: bytes, mime: str, sha256: str
) -> StoredObject:
    request = Request(
        _object_url(key), data=data, headers=_headers(mime), method="POST"
    )
    try:
        with urlopen(request, timeout=30) as response:
            if response.status not in {200, 201}:
                raise StorageError("STORAGE_UPLOAD_FAILED")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise StorageError("STORAGE_UPLOAD_FAILED") from exc
    return StoredObject(key=key, version=sha256)


def delete_private_object(key: str) -> None:
    request = Request(_object_url(key), headers=_headers(), method="DELETE")
    try:
        with urlopen(request, timeout=15):
            return
    except (HTTPError, URLError, TimeoutError) as exc:
        raise StorageError("STORAGE_COMPENSATION_FAILED") from exc
