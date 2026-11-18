from __future__ import annotations

import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from api_core.worker import (
    process_idempotency_cleanup,
    process_resource_batch,
    process_sla_batch,
    request_delegation_tick,
    run_outbox_batch,
)
from api_core.workflow.ai_learning import run_pending as run_learning_jobs

logger = logging.getLogger(__name__)


def _learn_from_feedback_if_new() -> None:
    """Học dồn hằng ngày khi có lựa chọn mới của quản lý; lỗi không làm dừng worker."""
    from django.db import connection

    from api_core.workflow import ai_feedback

    try:
        with connection.cursor() as cursor:
            if ai_feedback.new_ranking_feedback_count(cursor) == 0:
                return
        result = ai_feedback.learn_from_feedback()
        logger.info("ai_feedback_learning status=%s", result.get("status"))
    except Exception:
        logger.warning("ai_feedback_learning_failed", exc_info=True)


class Command(BaseCommand):
    help = "Claim and deliver EAS outbox events with lease/retry semantics."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        poll_seconds = options["poll_seconds"]
        if not 1 <= batch_size <= 100 or not 0.1 <= poll_seconds <= 30:
            raise CommandError("Unsafe worker arguments")

        running = True

        def _signal_handler(signum, frame):
            nonlocal running
            logger.info(
                "Outbox worker received signal %s, exiting gracefully...", signum
            )
            running = False

        try:
            signal.signal(signal.SIGTERM, _signal_handler)
            signal.signal(signal.SIGINT, _signal_handler)
        except (ValueError, AttributeError):
            pass

        next_delegation_tick = 0.0
        next_feedback_learning = (
            time.monotonic() + 600
        )  # lần đầu sau 10 phút, sau đó mỗi ngày
        while running:
            close_old_connections()
            try:
                sla_events = process_sla_batch(batch_size=min(batch_size * 5, 500))
                # Borrowed rooms / vehicles / equipment go back when the period ends.
                sla_events += process_resource_batch()
                # Delegations that started: waiting steps go to the delegate.
                if time.monotonic() >= next_delegation_tick:
                    sla_events += request_delegation_tick()
                    next_delegation_tick = time.monotonic() + 60
                # Expired idempotency responses / tombstones (no events emitted).
                process_idempotency_cleanup()
                processed = run_outbox_batch(batch_size=batch_size)
                # AI regulation learning jobs (leased: safe alongside API runners).
                processed += run_learning_jobs()
                if time.monotonic() >= next_feedback_learning:
                    next_feedback_learning = time.monotonic() + 24 * 3600
                    _learn_from_feedback_if_new()
            except Exception:
                logger.exception("Error processing worker batch")
                if options["once"]:
                    raise
                time.sleep(poll_seconds)
                continue

            if options["once"]:
                self.stdout.write(f"sla_events={sla_events} outbox_events={processed}")
                return
            if processed == 0 and sla_events == 0 and running:
                time.sleep(poll_seconds)
