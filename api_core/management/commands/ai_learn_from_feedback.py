"""Học dồn từ phản hồi của con người: huấn luyện lại mô hình xếp hạng (có cổng) + đề xuất chỉnh ngưỡng.

  python manage.py ai_learn_from_feedback          # chạy ngay
  python manage.py ai_learn_from_feedback --summary  # chỉ xem thống kê phản hồi, không huấn luyện
Worker tự chạy mỗi ngày khi có phản hồi mới (run_outbox_worker).
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.db import connection

from api_core.workflow import ai_feedback


class Command(BaseCommand):
    help = "Học dồn từ phản hồi của con người (mô hình xếp hạng + đề xuất ngưỡng)."

    def add_arguments(self, parser):
        parser.add_argument("--summary", action="store_true")

    def handle(self, *args, **options):
        if options["summary"]:
            with connection.cursor() as cursor:
                result = ai_feedback.feedback_summary(cursor)
        else:
            result = ai_feedback.learn_from_feedback()
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=1, default=str))
