import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

os.environ['DJANGO_SETTINGS_MODULE'] = 'api_core.config.settings'
import django
django.setup()

from django.db import connection
from django.core.cache import cache

with connection.cursor() as cursor:
    cursor.execute("""
        UPDATE eas.ai_system_state
        SET client_maintenance_lock = false,
            sync_status = 'COMPLETED',
            progress_percent = 100,
            current_step_index = 4,
            current_step_label = 'Hoàn tất cập nhật quy định'
        WHERE id = 1
    """)
cache.clear()
print("ai_system_state unlocked and cache cleared successfully!")
