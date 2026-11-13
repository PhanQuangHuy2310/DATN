"""Load shared reference data into Redis so the first page visit after a
deploy does not wait on the database. Read-only; safe to run any time."""

import time

from django.core.management.base import BaseCommand

from api_core.read_cache import cached


class Command(BaseCommand):
    help = "Warm the Redis read cache with shared reference data."

    def handle(self, *args, **options):
        from api_core.administration import org_users_rbac, regulations_ai, workflows
        from api_core.administration.workspace import _catalog_items

        loaders = {
            "request-catalog": (_catalog_items,),
            "workflow-categories": (workflows._categories,),
            "request-templates": (workflows._fetch_types, ""),
            "regulations": (regulations_ai._list_regulations,),
            "org-chart-tree": (org_users_rbac._org_chart_rows,),
        }
        for name, (loader, *parts) in loaders.items():
            started = time.monotonic()
            try:
                cached(name, loader, *parts)
                ms = round((time.monotonic() - started) * 1000)
                self.stdout.write(f"warm {name}: {ms} ms")
            except Exception as exc:  # noqa: BLE001 - one bad loader must not stop the rest
                self.stderr.write(f"warm {name} failed: {type(exc).__name__}")
