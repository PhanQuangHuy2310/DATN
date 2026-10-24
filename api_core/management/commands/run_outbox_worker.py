from __future__ import annotations

import logging
import signal
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from api_core.worker import process_sla_batch, run_outbox_batch

logger = logging.getLogger(__name__)


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

        while running:
            close_old_connections()
            try:
                sla_events = process_sla_batch(batch_size=min(batch_size * 5, 500))
                processed = run_outbox_batch(batch_size=batch_size)
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
