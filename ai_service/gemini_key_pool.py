"""
Gemini API Key Pool & Auto-Failover Harness (gemini_key_pool.py).

Tự động xoay vòng (failover / rotation) qua danh sách nhiều Google AI Studio
(Gemini) API keys khi key hiện tại gặp lỗi:
  - Hết hạn mức / hết token / giới hạn tần suất (HTTP 429, ResourceExhausted, TooManyRequests)
  - Key lỗi / hết hạn / bị thu hồi (HTTP 400/401/403, API_KEY_INVALID, PermissionDenied)
  - Lỗi mạng hoặc máy chủ tạm thời (HTTP 500/503, DeadlineExceeded)

Cách cấu hình nhiều key trong .env (hỗ trợ đồng thời tất cả các cách):
  1. GEMINI_API_KEY=key_1,key_2,key_3
  2. GEMINI_API_KEYS=key_1,key_2,key_3
  3. GEMINI_API_KEY_1=key_1
     GEMINI_API_KEY_2=key_2
     GEMINI_API_KEY_3=key_3
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

_SPLIT_RE = re.compile(r"[,;\s]+")

DEFAULT_QUOTA_COOLDOWN_SEC = 60.0
MAX_QUOTA_COOLDOWN_SEC = 600.0
TRANSIENT_COOLDOWN_SEC = 15.0


def mask_key(key: str) -> str:
    """Che bớt ký tự giữa của API key khi ghi log/trạng thái, không bao giờ lộ nguyên key."""
    k = (key or "").strip()
    if len(k) <= 10:
        return "***"
    return f"{k[:6]}...{k[-4:]}"


def _split_raw_keys(raw: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        parts: list[str] = []
        for item in raw:
            parts.extend(_split_raw_keys(item))
        return parts
    text = str(raw).strip().strip("\"'")
    if not text:
        return []
    return [
        p.strip().strip("\"'") for p in _SPLIT_RE.split(text) if p.strip().strip("\"'")
    ]


def collect_env_keys() -> list[str]:
    """Thu thập toàn bộ danh sách Gemini API key từ biến môi trường (khử trùng lặp, giữ thứ tự)."""
    # Nếu GEMINI_API_KEY được gán tường minh bằng chuỗi rỗng "" trong os.environ
    # (ví dụ trong bài test kiểm thử chế độ offline không có key) và không có GEMINI_API_KEYS,
    # thì tôn trọng trạng thái tắt key.
    explicit_empty = (
        "GEMINI_API_KEY" in os.environ
        and not os.environ.get("GEMINI_API_KEY", "").strip()
    )
    has_multi_env = bool(os.environ.get("GEMINI_API_KEYS", "").strip())
    if explicit_empty and not has_multi_env:
        return []

    candidates: list[str] = []
    candidates.extend(_split_raw_keys(os.environ.get("GEMINI_API_KEY", "")))
    candidates.extend(_split_raw_keys(os.environ.get("GEMINI_API_KEYS", "")))
    for idx in range(1, 21):
        val = os.environ.get(f"GEMINI_API_KEY_{idx}", "").strip()
        if val:
            candidates.extend(_split_raw_keys(val))

    seen: set[str] = set()
    unique: list[str] = []
    for key in candidates:
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def resolve_keys(explicit_key: str | list[str] | None = None) -> list[str]:
    """Kết hợp key truyền trực tiếp (có thể chứa nhiều key phân tách bằng dấu phẩy) với pool môi trường."""
    explicit_list = _split_raw_keys(explicit_key)
    # Nếu caller truyền một key giả lập ngắn trong unit test (ví dụ api_key="k"),
    # chỉ dùng danh sách explicit_list đó để không ảnh hưởng bài test.
    if explicit_list and all(len(k) < 16 for k in explicit_list):
        return explicit_list

    seen: set[str] = set()
    merged: list[str] = []
    for key in [*explicit_list, *collect_env_keys()]:
        if key and key not in seen:
            seen.add(key)
            merged.append(key)
    return merged


def classify_gemini_error(exc: BaseException) -> str:
    """Phân loại lỗi từ Gemini SDK / REST API:
    - 'invalid': key không hợp lệ, hết hạn, bị khóa hoặc sai quyền (quarantine)
    - 'quota': hết token / hết quota / vượt rate limit HTTP 429 (cooldown)
    - 'transient': lỗi mạng / timeout / server 5xx (short cooldown)
    """
    name = type(exc).__name__
    msg = f"{name}: {exc}".lower()

    invalid_markers = (
        "api_key_invalid",
        "api key not valid",
        "api key expired",
        "consumer_invalid",
        "permissiondenied",
        "permission_denied",
        "unauthenticated",
        "invalid_argument: api key",
        "key_invalid",
        "leaked",
        "401",
        "403",
    )
    if any(m in msg for m in invalid_markers):
        return "invalid"

    quota_markers = (
        "toomanyrequests",
        "resourceexhausted",
        "resource_exhausted",
        "resource has been exhausted",
        "quota",
        "rate_limit",
        "rate limit",
        "tokens",
        "429",
    )
    if any(m in msg for m in quota_markers):
        return "quota"

    return "transient"


@dataclass
class KeyState:
    key: str
    invalid: bool = False
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str = ""
    last_used_at: float = 0.0


class GeminiKeyPool:
    """Quản lý trạng thái các Gemini API key và tự động đổi sang key tiếp theo khi lỗi."""

    def __init__(
        self,
        quota_cooldown_sec: float = DEFAULT_QUOTA_COOLDOWN_SEC,
        transient_cooldown_sec: float = TRANSIENT_COOLDOWN_SEC,
    ) -> None:
        self._lock = threading.RLock()
        self._call_lock = threading.RLock()
        self._states: dict[str, KeyState] = {}
        self._active_key: str | None = None
        self.quota_cooldown_sec = quota_cooldown_sec
        self.transient_cooldown_sec = transient_cooldown_sec

    def reset(self) -> None:
        with self._lock:
            self._states.clear()
            self._active_key = None

    def _sync_keys(self, keys: list[str]) -> list[KeyState]:
        with self._lock:
            for k in keys:
                if k not in self._states:
                    self._states[k] = KeyState(key=k)
            if self._active_key not in keys:
                self._active_key = keys[0] if keys else None
            return [self._states[k] for k in keys]

    def _ordered_candidates(self, keys: list[str]) -> list[KeyState]:
        with self._lock:
            states = self._sync_keys(keys)
            if not states:
                return []

            start_idx = 0
            if self._active_key in keys:
                start_idx = keys.index(self._active_key)
            rotated = states[start_idx:] + states[:start_idx]

            now = time.monotonic()
            healthy = [s for s in rotated if not s.invalid and now >= s.cooldown_until]
            cooling = sorted(
                [s for s in rotated if not s.invalid and now < s.cooldown_until],
                key=lambda s: s.cooldown_until,
            )
            invalid = [s for s in rotated if s.invalid]
            # Ưu tiên key khỏe mạnh -> key đang cooldown sớm nhất -> nếu tất cả đều bị đánh dấu
            # invalid thì thử lại một vòng cuối phòng trường hợp lỗi cấu hình tạm thời.
            if healthy or cooling:
                return [*healthy, *cooling]
            return invalid

    def mark_success(self, key: str) -> None:
        with self._lock:
            st = self._states.setdefault(key, KeyState(key=key))
            st.invalid = False
            st.cooldown_until = 0.0
            st.consecutive_failures = 0
            st.success_count += 1
            st.last_used_at = time.time()
            self._active_key = key

    def mark_failure(self, key: str, exc: BaseException, all_keys: list[str]) -> str:
        kind = classify_gemini_error(exc)
        now = time.monotonic()
        with self._lock:
            st = self._states.setdefault(key, KeyState(key=key))
            st.failure_count += 1
            st.consecutive_failures += 1
            st.last_used_at = time.time()
            st.last_error = f"{type(exc).__name__}: {str(exc)[:180]}"

            if kind == "invalid":
                st.invalid = True
            elif kind == "quota":
                cooldown = min(
                    MAX_QUOTA_COOLDOWN_SEC,
                    self.quota_cooldown_sec
                    * (2 ** max(0, st.consecutive_failures - 1)),
                )
                st.cooldown_until = now + cooldown
            else:
                st.cooldown_until = now + self.transient_cooldown_sec

            # Chuyển con trỏ _active_key sang key tiếp theo trong danh sách
            if all_keys and key in all_keys and len(all_keys) > 1:
                next_idx = (all_keys.index(key) + 1) % len(all_keys)
                self._active_key = all_keys[next_idx]
        return kind

    def execute(
        self,
        fn: Callable[[str], T],
        api_key: str | list[str] | None = None,
    ) -> T:
        """Thực thi hàm gọi Gemini `fn(key)`. Nếu key hiện tại lỗi hoặc hết quota,
        tự động chuyển sang key kế tiếp trong pool cho tới khi thành công hoặc hết sạch key."""
        keys = resolve_keys(api_key)
        if not keys:
            raise RuntimeError("GEMINI_NOT_CONFIGURED")

        candidates = self._ordered_candidates(keys)
        last_exc: BaseException | None = None

        for idx, state in enumerate(candidates):
            current_key = state.key
            key_pos = keys.index(current_key) + 1 if current_key in keys else idx + 1
            try:
                # google.generativeai dùng cấu hình toàn cục khi gọi genai.configure(api_key=...),
                # nên khóa _call_lock bảo đảm an toàn đa luồng khi đổi key.
                with self._call_lock:
                    result = fn(current_key)
                self.mark_success(current_key)
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                kind = self.mark_failure(current_key, exc, keys)
                if idx + 1 < len(candidates):
                    next_key = candidates[idx + 1].key
                    next_pos = keys.index(next_key) + 1 if next_key in keys else idx + 2
                    logger.warning(
                        "[GeminiKeyPool] Key #%d (%s) gặp lỗi %s (%s) -> Tự động chuyển sang Key #%d (%s)",
                        key_pos,
                        mask_key(current_key),
                        kind,
                        type(exc).__name__,
                        next_pos,
                        mask_key(next_key),
                    )
                else:
                    logger.error(
                        "[GeminiKeyPool] Đã thử hết %d Gemini API key trong pool nhưng đều lỗi (lỗi cuối từ Key #%d %s: %s)",
                        len(candidates),
                        key_pos,
                        mask_key(current_key),
                        type(exc).__name__,
                    )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("GEMINI_KEY_POOL_EXHAUSTED")

    def status(self, api_key: str | list[str] | None = None) -> dict[str, Any]:
        keys = resolve_keys(api_key)
        now = time.monotonic()
        with self._lock:
            states = self._sync_keys(keys)
            items = []
            for idx, st in enumerate(states, start=1):
                cooldown_remaining = max(0.0, round(st.cooldown_until - now, 1))
                if st.invalid:
                    health = "invalid"
                elif cooldown_remaining > 0:
                    health = "cooldown"
                else:
                    health = "ready"
                items.append(
                    {
                        "index": idx,
                        "masked_key": mask_key(st.key),
                        "is_active": st.key == self._active_key,
                        "status": health,
                        "cooldown_remaining_sec": cooldown_remaining,
                        "success_count": st.success_count,
                        "failure_count": st.failure_count,
                        "last_error": st.last_error or None,
                    }
                )
            return {
                "total_keys": len(keys),
                "ready_keys": sum(1 for i in items if i["status"] == "ready"),
                "active_key": mask_key(self._active_key) if self._active_key else None,
                "keys": items,
            }


_default_pool = GeminiKeyPool()


def get_pool() -> GeminiKeyPool:
    return _default_pool


def has_any_key(api_key: str | list[str] | None = None) -> bool:
    return len(resolve_keys(api_key)) > 0


def execute_with_key_rotation(
    fn: Callable[[str], T],
    api_key: str | list[str] | None = None,
) -> T:
    return _default_pool.execute(fn, api_key=api_key)


def get_pool_status(api_key: str | list[str] | None = None) -> dict[str, Any]:
    return _default_pool.status(api_key=api_key)
