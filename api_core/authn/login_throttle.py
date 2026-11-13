"""Fail-closed dual-dimension login throttling (SRS NFR01).

Each *account* is limited across all IPs, and each *IP* is limited across all
email addresses. Only the trusted socket address is used: client-provided XFF must
not be trusted unless middleware has already established a trusted peer.
Keys never contain raw email addresses or IP addresses; TTL is a fixed window.
"""

from __future__ import annotations

from hashlib import sha256


def throttle_keys(email: str, remote_addr: str) -> tuple[str, str]:
    normalized_name = email.strip().casefold()
    addr = remote_addr.strip() or "unknown"
    user_digest = sha256(normalized_name.encode("utf-8")).hexdigest()
    ip_digest = sha256(addr.encode("utf-8")).hexdigest()
    return f"eas:login:account:{user_digest}", f"eas:login:ip:{ip_digest}"


def is_throttled(
    store, keys: tuple[str, str], *, account_limit: int, ip_limit: int
) -> bool:
    return (
        int(store.get(keys[0], 0) or 0) >= account_limit
        or int(store.get(keys[1], 0) or 0) >= ip_limit
    )


def incr_window(store, key: str, window_seconds: int) -> int:
    """Fixed-window counter that never leaves a key without an expiry.

    If the key expires between ``add`` and ``incr``, Redis INCRBY recreates it
    with no TTL and the client would stay blocked forever; re-arm the window.
    """
    if store.add(key, 1, timeout=window_seconds):
        return 1
    try:
        value = store.incr(key)
    except ValueError:
        store.add(key, 1, timeout=window_seconds)
        return 1
    ttl = getattr(store, "ttl", None)  # django-redis only; LocMem has no TTL API
    if ttl is not None and ttl(key) is None:
        store.expire(key, window_seconds)
    return value


def register_login_failure(
    store, keys: tuple[str, str], *, window_seconds: int
) -> None:
    """Atomic counter increment on Redis/Django cache, fixed window for each key."""
    for key in keys:
        incr_window(store, key, window_seconds)


def clear_account_failures(store, keys: tuple[str, str]) -> None:
    # Preserve the IP budget on success so attackers cannot reset the global
    # per-IP throttling budget with a valid account in between attempts.
    store.delete(keys[0])
