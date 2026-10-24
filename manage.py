#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main() -> None:
    if "test" in sys.argv:
        os.environ.setdefault("EAS_ENV", "test")
    else:
        try:
            from dotenv import load_dotenv

            env_candidate = Path(__file__).resolve().parent / "api_core" / ".env"
            if not env_candidate.is_file():
                env_candidate = Path(__file__).resolve().parent / ".env"
            if env_candidate.is_file():
                load_dotenv(env_candidate, override=False)
        except ImportError:
            pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
