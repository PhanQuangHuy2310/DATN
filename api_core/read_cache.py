"""Short-lived Redis cache for shared, rarely-changing reads (catalog, templates,
regulations, org chart).

Only the DB fetch is cached; authentication, role checks and per-user shaping
still run on every request. Every successful write through the API bumps one
version number, so a cached value never outlives an EAS write; the TTL bounds
staleness from writers outside the API (worker, Mock Systems, SQL run by hand).
"""

import logging
import time

from django.core.cache import cache

log = logging.getLogger(__name__)

VERSION_KEY = "eas:readcache:version"
TTL_SECONDS = (
    1800  # every API write bumps the version, so entries rarely live this long
)


def version() -> int:
    return cache.get(VERSION_KEY) or 0


def cached(name: str, loader, *parts):
    key = f"eas:readcache:{version()}:{name}:" + ":".join(str(p) for p in parts)
    value = cache.get(key)
    if value is None:
        value = loader()
        cache.set(key, value, timeout=TTL_SECONDS)
    return value


def invalidate() -> None:
    """Bump the version. Runs after a committed write, so it must never raise."""
    try:
        # add() is atomic, so concurrent bumps never collapse into one.
        cache.add(VERSION_KEY, 0, timeout=None)
        cache.incr(VERSION_KEY)
    except ValueError:  # evicted (allkeys-lru) between add and incr
        cache.set(VERSION_KEY, int(time.time()), timeout=None)
    except Exception:  # noqa: BLE001 - cache down: entries still expire by TTL
        log.warning("Read cache version bump failed; entries expire within TTL")
