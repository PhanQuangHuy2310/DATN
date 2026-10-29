"""Read-only request menu deployment check. Does not print secrets or alter DB."""
from __future__ import annotations

import json
from pathlib import Path

from connect_database import load_environment, database_url

ROOT = Path(__file__).resolve().parent
TYPES = json.loads((ROOT / 'api_core/catalog/approval_menu.json').read_text(encoding='utf-8'))['types']


def main() -> int:
    load_environment(ROOT / '.env.database')
    try:
        import psycopg
    except ImportError:
        print('Thiếu psycopg. Cài dependencies Backend bằng api_core/requirements.txt.')
        return 2
    try:
        with psycopg.connect(database_url(), connect_timeout=10, prepare_threshold=None) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                codes = [t['code'] for t in TYPES]
                cursor.execute('''
                    SELECT rt.code, rt.lifecycle, rt.is_active,
                           COALESCE(cr.state, '')
                    FROM eas.request_type rt
                    LEFT JOIN eas.config_release cr ON cr.id = rt.active_release_id
                    WHERE rt.code = ANY(%s::text[])
                ''', (codes,))
                actual = {code: (life, active, state) for code, life, active, state in cursor.fetchall()}
                print('KIỂM TRA DANH MỤC YÊU CẦU (CHỈ ĐỌC)')
                count = 0
                for t in TYPES:
                    code, life = t['code'], t['lifecycle']
                    got = actual.get(code)
                    status = ('CHƯA ĐĂNG KÝ' if got is None else
                              'SAI MẪU VÒNG ĐỜI' if got[0] != life else
                              'CHƯA KÍCH HOẠT' if not got[1] else
                              'CHƯA CÓ BẢN PHÁT HÀNH' if got[2] != 'PUBLISHED' else
                              'ĐÃ CÔNG BỐ')
                    count += status == 'ĐÃ CÔNG BỐ'
                    print(f'{code:<28} | {life} | {status}')
                print(f'Kết quả: {count}/{len(TYPES)} mã có bản phát hành đang hoạt động.')
        return 0
    except Exception as err:
        # Credentials, query parameters and hostnames are not printed.
        print(f'Kiểm tra thất bại: {type(err).__name__}. Kiểm tra Terminal Backend hoặc kết nối Supabase.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
