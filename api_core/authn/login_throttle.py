"""Fail-closed dual-dimension login throttling (SRS NFR01).

Each *account* is limited across all IPs, and each *IP* is limited across all
usernames. Only the trusted socket address is used: client-provided XFF must
not be trusted unless middleware has already established a trusted peer.
Keys never contain raw usernames or IP addresses; TTL is a fixed window.
"""
from __future__ import annotations

from hashlib import sha256


def throttle_keys(username: str, remote_addr: str) -> tuple[str, str]:
    normalized_name = username.strip().casefold()
    addr = remote_addr.strip() or "unknown"
    user_digest = sha256(normalized_name.encode("utf-8")).hexdigest()
    ip_digest = sha256(addr.encode("utf-8")).hexdigest()
    return f"eas:login:account:{user_digest}", f"eas:login:ip:{ip_digest}"


def is_throttled(store, keys: tuple[str, str], *, account_limit: int, ip_limit: int) -> bool:
    return int(store.get(keys[0], 0) or 0) >= account_limit or int(store.get(keys[1], 0) or 0) >= ip_limit


def register_login_failure(store, keys: tuple[str, str], *, window_seconds: int) -> None:
    """Atomic counter increment on Redis/Django cache, fixed window for each key."""
    for key in keys:
        if store.add(key, 1, timeout=window_seconds):
            continue
        try:
            store.incr(key)
        except ValueError:
            # Key expired between add and incr. Do not lose this failure.
            store.add(key, 1, timeout=window_seconds)


def clear_account_failures(store, keys: tuple[str, str]) -> None:
    # Preserve the IP budget on success so attackers cannot reset the global
    # per-IP throttling budget with a valid account in between attempts.
    store.delete(keys[0])
