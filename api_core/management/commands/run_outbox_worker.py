from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError

from api_core.worker import process_sla_batch, run_outbox_batch


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
        while True:
            sla_events = process_sla_batch(batch_size=min(batch_size * 5, 500))
            processed = run_outbox_batch(batch_size=batch_size)
            if options["once"]:
                self.stdout.write(f"sla_events={sla_events} outbox_events={processed}")
                return
            if processed == 0 and sla_events == 0:
                time.sleep(poll_seconds)
