"""Opt-in, SQL-text-free timing of DB calls inside one HTTP request."""
from __future__ import annotations

from time import perf_counter


class QueryTiming:
    def __init__(self):
        self.count = 0
        self.duration_ms = 0.0
        self.max_ms = 0.0

    def __call__(self, execute, sql, params, many, context):
        start = perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed = (perf_counter() - start) * 1000
            self.count += 1
            self.duration_ms += elapsed
            self.max_ms = max(self.max_ms, elapsed)
