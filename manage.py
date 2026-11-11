#!/usr/bin/env python
import os
import sys


def main() -> None:
    if "test" in sys.argv:
        os.environ.setdefault("EAS_ENV", "test")
    else:
        from project_env import load_project_env

        load_project_env()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
