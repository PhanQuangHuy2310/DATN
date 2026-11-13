"""Short-lived Redis cache for shared, rarely-changing reads (catalog, templates,
regulations, org chart).

Only the DB fetch is cached; authentication, role checks and per-user shaping
still run on every request. Every successful write through the API bumps one
version number, so a cached value never outlives an EAS write; the TTL bounds
staleness from writers outside the API (worker, Mock Systems, SQL run by hand).
"""

from django.core.cache import cache

VERSION_KEY = "eas:readcache:version"
TTL_SECONDS = 60


def cached(name: str, loader, *parts):
    version = cache.get(VERSION_KEY) or 0
    key = f"eas:readcache:{version}:{name}:" + ":".join(str(p) for p in parts)
    value = cache.get(key)
    if value is None:
        value = loader()
        cache.set(key, value, timeout=TTL_SECONDS)
    return value


def invalidate() -> None:
    cache.add(VERSION_KEY, 0, timeout=None)  # atomic: concurrent bumps never collapse
    cache.incr(VERSION_KEY)
