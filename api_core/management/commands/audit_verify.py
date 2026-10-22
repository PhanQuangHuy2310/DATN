from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand

from api_core.workflow.reporting import verify_audit_chain


class Command(BaseCommand):
    help = "Verify cryptographic tamper-evident hash chain for audit events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            required=True,
            help="Scope key to verify (e.g., REQ:<uuid> or ADMIN).",
        )
        parser.add_argument(
            "--checkpoint", required=False, help="Optional checkpoint reference."
        )

    def handle(self, *args, **options):
        scope = options["scope"].strip()
        result = verify_audit_chain(scope)

        self.stdout.write(json.dumps(result, indent=2))
        if result.get("status") == "PASS":
            sys.exit(0)
        else:
            sys.exit(2)
