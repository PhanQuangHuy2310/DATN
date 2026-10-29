from __future__ import annotations

from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _register_psycopg_json_loaders(sender, connection, **kwargs) -> None:
    if (
        getattr(connection, "vendor", None) != "postgresql"
        or getattr(connection, "connection", None) is None
    ):
        return
    try:
        from psycopg.types.json import (
            JsonbBinaryLoader,
            JsonBinaryLoader,
            JsonbLoader,
            JsonLoader,
        )

        adapters = connection.connection.adapters
        adapters.register_loader("json", JsonLoader)
        adapters.register_loader("jsonb", JsonbLoader)
        adapters.register_loader("json", JsonBinaryLoader)
        adapters.register_loader("jsonb", JsonbBinaryLoader)
    except (ImportError, AttributeError, TypeError):
        return


class ApiCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api_core"

    def ready(self) -> None:
        connection_created.connect(
            _register_psycopg_json_loaders,
            dispatch_uid="api_core.register_psycopg_json_loaders",
        )
