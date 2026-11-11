#!/usr/bin/env python3
"""Fail fast if a configured shared Redis cache is unavailable.

Used only by the local Windows backend launcher.  No credentials are logged,
no configuration is changed and the probe expires after five seconds.
"""
from __future__ import annotations

import os
import sys
import time
from uuid import uuid4


def check_cache(cache_backend, cache_obj, *, sleep=time.sleep) -> bool:
    """Probe the *configured* Django cache, not just an open TCP port."""
    if "redis" not in cache_backend.lower():
        print("CACHE OK: local development cache (not suitable for multi-worker production).")
        return True
    key = "eas:local:cache-preflight:" + uuid4().hex
    for attempt in range(3):
        try:
            cache_obj.set(key, "OK", timeout=5)
            if cache_obj.get(key) == "OK":
                print("CACHE OK: Django can write/read Redis.")
                return True
        except Exception as exc:
            # Do not render exception arguments: URLs may contain secrets.
            print(f"CACHE NOT READY ({type(exc).__name__}), attempt {attempt + 1}/3.")
        if attempt < 2:
            sleep(1)
    print("CACHE ERROR: Redis is configured but Django cannot write/read it.")
    print("Run: docker compose up -d redis")
    print("Then: docker compose exec redis redis-cli ping")
    print("Check Redis host/port and restart the local backend.")
    return False


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    try:
        from django.conf import settings
        from django.core.cache import cache
        return 0 if check_cache(settings.CACHES["default"]["BACKEND"], cache) else 1
    except Exception as exc:
        print(f"CACHE CONFIG ERROR: {type(exc).__name__}. Check Django settings and .env.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
