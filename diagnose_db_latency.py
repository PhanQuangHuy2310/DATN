"""Read-only latency probe for EAS PostgreSQL / Supabase (Windows CMD).

Run from the project root:
    .venv\\Scripts\\python.exe diagnose_db_latency.py --samples 8

Uses the same credentials as connect_database.py, but never prints them.
Each sample opens a NEW TLS connection to distinguish pooler connectivity
from the execution time of SELECT 1. No schema change, no business data read.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import sys
import time

from connect_database import ConfigurationError, database_url, load_environment
from api_core.db_diagnostics import failure_category, sqlstate


def quantile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[int((len(values) - 1) * 0.95)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Supabase latency/connectivity probe")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--connect-timeout", type=int, default=6)
    args = parser.parse_args(argv)
    if not (1 <= args.samples <= 30 and 0 <= args.interval <= 10 and 2 <= args.connect_timeout <= 20):
        parser.error("samples must be 1..30, interval 0..10, connect-timeout 2..20")
    try:
        load_environment(Path(__file__).with_name('.env.database'))
        url = database_url()
    except ConfigurationError as exc:
        print(f"CONFIG: {exc}")
        return 2
    try:
        import psycopg
    except ImportError:
        print('Missing psycopg: install api_core\\requirements.txt into .venv')
        return 2

    connect_ms, query_ms = [], []
    failures: dict[str, int] = {}
    print(f"Read-only connectivity test: {args.samples} samples; connection and SELECT 1 only")
    for i in range(args.samples):
        t0 = time.perf_counter()
        try:
            with psycopg.connect(
                url, connect_timeout=args.connect_timeout, prepare_threshold=None,
                application_name="eas_readonly_latency_probe",
            ) as conn:
                connected_at = time.perf_counter()
                with conn.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() != (1,):
                        raise RuntimeError("Unexpected response to SELECT 1")
                finished_at = time.perf_counter()
            c_ms = (connected_at - t0) * 1000
            q_ms = (finished_at - connected_at) * 1000
            connect_ms.append(c_ms)
            query_ms.append(q_ms)
            print(f"  {i+1:02d}: OK  connect={c_ms:.0f}ms  select={q_ms:.0f}ms")
        except (psycopg.Error, OSError, TimeoutError) as exc:
            category = failure_category(exc)
            state = sqlstate(exc)
            failures[category] = failures.get(category, 0) + 1
            print(f"  {i+1:02d}: FAIL category={category} SQLSTATE={state}")
        if i < args.samples - 1:
            time.sleep(args.interval)
    if connect_ms:
        print(f"Successful samples={len(connect_ms)}/{args.samples}")
        print(f"Connect median={statistics.median(connect_ms):.0f}ms p95~={quantile_95(connect_ms):.0f}ms")
        print(f"SELECT median={statistics.median(query_ms):.0f}ms p95~={quantile_95(query_ms):.0f}ms")
    print(f"Failures by category: {failures}")
    if failures:
        print("Connection failures indicate network / pooler / database capacity; not evidence of slow SQL.")
        return 1
    print("All samples succeeded. Investigate specific business query latency if the UI is still slow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
