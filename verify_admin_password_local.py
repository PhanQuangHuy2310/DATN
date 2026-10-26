r"""Read-only Django password check. No HTTP login/rate limiting, no DB writes.
CMD: .\.venv\Scripts\python.exe verify_admin_password_local.py admin
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

from connect_database import database_url, load_environment

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "admin"
    load_environment(Path(__file__).with_name(".env.database"))
    os.environ["DATABASE_URL"] = database_url()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    import django

    django.setup()
    from django.contrib.auth.hashers import check_password

    from api_core.authn.service import find_user

    obj = find_user(user)
    print("USER_EXISTS:", bool(obj))
    print("ACTIVE:", bool(obj.is_active) if obj else False)
    if obj:
        password = getpass.getpass("Password (hidden): ")
        print("PASSWORD_MATCH:", bool(check_password(password, obj.password_hash)))
        del password
