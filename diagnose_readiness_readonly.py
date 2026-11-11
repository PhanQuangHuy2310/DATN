"""Read-only diagnosis for EAS /health/ready 503 (Windows: python diagnose_readiness_readonly.py).

Never writes to database and never prints DB credentials or full error messages.
Uses the same .env as connect_database.py. All checks are independent
of a browser session and require no admin privileges beyond SELECT/metadata.
"""
from __future__ import annotations

import os
from pathlib import Path

from api_core.health.schema_contract import (
    REQUIRED_EAS_TABLES,
    missing_required_eas_tables,
)
from api_core.health.request_type_readiness import assess_request_types
from connect_database import database_url, load_environment


def _invalid_release_reason(has_release: bool, state: str) -> str:
    if not has_release:
        return 'chua gan active_release_id'
    if state != 'PUBLISHED':
        return 'release khong PUBLISHED'
    return 'release khong khop type_id/lifecycle'

def run() -> int:
    load_environment(Path(__file__).with_name('.env'))
    try:
        import psycopg
    except ImportError:
        print('[FAIL] psycopg chua duoc cai. Cai backend requirements truoc.')
        return 2
    try:
        with psycopg.connect(
            database_url(), connect_timeout=10, prepare_threshold=None,
            options='-c statement_timeout=10000 -c lock_timeout=2500',
        ) as conn, conn.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                cur.execute("""
                    SELECT c.relname
                    FROM pg_catalog.pg_class AS c
                    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'eas' AND c.relkind IN ('r','p')
                    ORDER BY c.relname
                """)
                present = {r[0] for r in cur.fetchall()}
                missing = missing_required_eas_tables(present)
                extra = sorted(present - REQUIRED_EAS_TABLES)
                print(f'[INFO] eas: {len(present)} bang tong, {len(REQUIRED_EAS_TABLES)} bang bat buoc')
                print('[PASS] Day du 30 bang bat buoc.' if not missing else
                      '[FAIL] Thieu bang bat buoc: ' + ', '.join(missing))
                if extra:
                    print('[INFO] Bang bo sung hop le (chi hien thi): ' + ', '.join(extra))

                cur.execute("""
                    SELECT rt.code, rt.lifecycle,
                           rt.active_release_id IS NOT NULL AS has_active_release,
                           cr.state,
                           cr.id IS NOT NULL AND cr.state = 'PUBLISHED'
                             AND cr.type_id = rt.id
                             AND cr.lifecycle = rt.lifecycle AS release_valid
                    FROM eas.request_type AS rt
                    LEFT JOIN eas.config_release AS cr ON cr.id = rt.active_release_id
                    WHERE rt.is_active
                    ORDER BY rt.code
                """)
                rows = cur.fetchall()
                invalid = [r for r in rows if not r[4]]
                print(f'[INFO] request_type: {len(rows)} dang active; {len(invalid)} chua co release hop le')
                for code, lifecycle, has_release, state, _ in invalid:
                    detail = _invalid_release_reason(has_release, state)
                    print(f'[WARN] {code} (Template {lifecycle}): {detail}')
                if not invalid:
                    print('[PASS] Moi loai don active co release PUBLISHED phu hop.')
                required_active = os.environ.get('EAS_REQUIRE_ACTIVE_RELEASES','true').lower() == 'true'
                strict_full = os.environ.get('EAS_REQUIRE_FULL_CATALOG_READY','false').lower() == 'true'
                ready_checks = assess_request_types(
                    [(code, life, valid) for code, life, _, _, valid in rows],
                    require_active_releases=required_active,
                )
                print('[PASS] Ba loai P0 co mat.' if ready_checks['request_types_match_p0'] else
                      '[FAIL] Thieu loai P0 active hoac sai Template.')
                print('[PASS] Ba loai P0 co release hop le.' if ready_checks['p0_active_types_configured'] else
                      '[FAIL] Co loai P0 chua duoc publish release.')
                if invalid:
                    print('[WARN] Danh muc mo rong chua hoan chinh; khong the tao/gửi don cua nhung loai chua publish.')
                if strict_full:
                    print('[NOTE] EAS_REQUIRE_FULL_CATALOG_READY=true: yeu cau tat ca loai active phai co release.')
                else:
                    print('[INFO] EAS_REQUIRE_FULL_CATALOG_READY=false: warning danh muc khong ha HTTP readiness.')
                core = (not missing and ready_checks['request_types_match_p0']
                        and ready_checks['p0_active_types_configured'])
                if strict_full:
                    core = core and ready_checks['all_active_types_configured']
                if core:
                    print('[PASS] Core catalog/schema readiness. Chua thay the check Redis/Storage/Mock tai /health/ready.')
                return 0 if core else 1
    except Exception as e:
        state = getattr(e, 'sqlstate', None) or getattr(getattr(e,'__cause__',None),'sqlstate',None)
        print('[FAIL] Khong the kiem tra, error_type='+type(e).__name__+
              ', SQLSTATE='+str(state or 'unknown'))
        return 2


if __name__ == '__main__':
    raise SystemExit(run())
