import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.settings")
django.setup()

from datetime import datetime, timedelta, timezone

from django.db import connection

VN_TZ = timezone(timedelta(hours=7))


def distribute_request_timestamps():
    """Distribute submitted requests so that day, week, month, and year periods all have rich, non-zero data."""
    now = datetime.now(VN_TZ)
    today_base = now.replace(hour=8, minute=30, second=0, microsecond=0)

    with connection.cursor() as cur:
        cur.execute(
            "SELECT id FROM eas.request WHERE status <> 'DRAFT' ORDER BY created_at"
        )
        req_ids = [row[0] for row in cur.fetchall()]
        print(f"Distributing timestamps for {len(req_ids)} submitted requests...")

        # Today (Day): 6 requests
        today_offsets = [
            timedelta(hours=0),
            timedelta(hours=1, minutes=15),
            timedelta(hours=2, minutes=30),
            timedelta(hours=4),
            timedelta(hours=5, minutes=45),
            timedelta(hours=7, minutes=10),
        ]

        # This week (Week, excluding today): 8 requests (yesterday)
        yesterday_base = (now - timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

        # This month (earlier this month): 6 requests (2 days ago)
        earlier_month_base = (now - timedelta(days=2)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        # Rest: previous months in 2026
        older_base = datetime(2026, 9, 15, 10, 0, 0, tzinfo=VN_TZ)

        for idx, rid in enumerate(req_ids):
            if idx < 6:
                ts = today_base + today_offsets[idx]
            elif idx < 14:
                ts = yesterday_base + timedelta(hours=(idx - 6) * 1)
            elif idx < 20:
                ts = earlier_month_base + timedelta(hours=(idx - 14) * 1)
            else:
                ts = older_base + timedelta(days=(idx - 20) * 3)

            cur.execute(
                "UPDATE eas.request SET created_at = %s, updated_at = %s WHERE id = %s",
                [ts, ts, rid],
            )
        print("Distributed request timestamps successfully.")


if __name__ == "__main__":
    distribute_request_timestamps()
