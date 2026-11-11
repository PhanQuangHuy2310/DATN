#!/usr/bin/env python
import os
import sys


def main() -> None:
    # VS Code (python.terminal.useEnvFile) or shell sessions can pre-load
    # EAS_ENV=development from .env; tests must use the isolated SQLite test
    # profile unless EAS_TEST_USE_POSTGRES=1 is explicitly requested.
    if "test" in sys.argv and os.environ.get("EAS_TEST_USE_POSTGRES") != "1":
        os.environ["EAS_ENV"] = "test"
    elif "test" not in sys.argv:
        from project_env import load_project_env

        load_project_env()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
