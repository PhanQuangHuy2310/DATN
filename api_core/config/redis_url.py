"""Resolve the Redis URL for processes running outside Docker.

REDIS_URL always wins (Docker sets redis://redis:6379/0). Outside Docker a
host/port can be given instead; the port defaults to 6380 so the compose
Redis (published on 127.0.0.1:6380) never collides with another Redis
already listening on the machine's default 6379.
"""

from __future__ import annotations

from collections.abc import Mapping

DEFAULT_LOCAL_PORT = 6380


def resolve_redis_url(environ: Mapping[str, str]) -> str:
    url = (environ.get("REDIS_URL") or "").strip()
    if url:
        return url
    host = (environ.get("EAS_REDIS_HOST") or "").strip()
    port = (environ.get("EAS_REDIS_PORT") or "").strip()
    if not host and not port:
        return ""  # no Redis configured: development uses the local-memory cache
    port_number = int(port or DEFAULT_LOCAL_PORT)
    if not 1 <= port_number <= 65535:
        raise RuntimeError("EAS_REDIS_PORT must be a valid TCP port")
    db = (environ.get("EAS_REDIS_DB") or "0").strip()
    return f"redis://{host or '127.0.0.1'}:{port_number}/{db}"
