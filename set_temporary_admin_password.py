r"""Create a one-time temporary password using EAS's existing audited reset.

Run in the EAS project root (same directory as manage.py):

  .\.venv\Scripts\python.exe set_temporary_admin_password.py --user admin \
      --operator admin --approval LOCAL-RECOVERY-20261027

Requirements:
- Run only as an authorized operator with appropriate access to this database.
- .env.database (or existing DB environment variables) must target the intended EAS DB.
- Relies on the project's api_core management command `account_reset`.
- The plaintext temporary password is printed ONCE after a confirmed DB commit.
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path


def generate_password(length: int = 24) -> str:
    if length < 16:
        raise ValueError("length must be at least 16")
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*_-+="
    alphabet = upper + lower + digits + symbols
    chars = [secrets.choice(group) for group in (upper, lower, digits, symbols)]
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an EAS temporary password, reset account with audit, force password change"
    )
    parser.add_argument("--user", default="admin", help="Account to reset (default: admin)")
    parser.add_argument("--operator", required=True, help="Authorized operator username, for audit")
    parser.add_argument("--approval", required=True, help="Authorized recovery ticket/reference")
    args = parser.parse_args()
    username = args.user.strip().lower()
    operator = args.operator.strip()
    approval = args.approval.strip()
    if not username or not operator or len(approval) < 10:
        parser.error("--user/--operator cannot be blank; --approval needs at least 10 characters")

    root = Path(__file__).resolve().parent
    if not (root / "manage.py").exists():
        parser.error("Copy this script into the DATN project root beside manage.py")

    try:
        from connect_database import database_url, load_environment

        load_environment(root / ".env.database")
        os.environ["DATABASE_URL"] = database_url()
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
        import django

        django.setup()
        from django.core.management import call_command
        from api_core.authn.service import validate_new_password
        from django.db import connection
    except Exception as exc:
        print(f"[ERROR] Khong tai duoc cau hinh EAS: {type(exc).__name__}", file=sys.stderr)
        return 2

    print(f"Tai khoan dich: {username}")
    print("Canh bao: Lenh thay doi mat khau tren DATABASE dang ket noi, vo hieu hoa phien cu.")
    print("Chi thuc hien neu ban co quyen quan tri database nay.")
    if input("Nhap RESET de xac nhan: ").strip() != "RESET":
        print("Da huy, khong thay doi gi.")
        return 1

    password = generate_password()
    # The generator has complexity guarantees; regenerate in the rare case it
    # contains the username or conflicts with the project's validator.
    for _ in range(30):
        try:
            validate_new_password(password, username)
            break
        except Exception:
            password = generate_password()
    else:
        print("[ERROR] Khong tao duoc mat khau thoa chinh sach.", file=sys.stderr)
        return 2

    try:
        os.environ["EAS_TEMP_PASSWORD"] = password
        try:
            call_command(
                "account_reset",
                user=username,
                mode="reset-password",
                operator=operator,
                approval=approval,
            )
        except SystemExit as exc:
            # Existing EAS management command exits with code 0 on success.
            if exc.code != 0:
                print("[ERROR] Reset khong thanh cong.", file=sys.stderr)
                return 3
    except Exception as exc:
        # Do not print exception content; it may contain database connectivity details.
        print(f"[ERROR] Reset that bai: {type(exc).__name__}", file=sys.stderr)
        return 3
    finally:
        os.environ.pop("EAS_TEMP_PASSWORD", None)

    # Confirm the forcing flag without retrieving or printing the stored hash.
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT must_change_password, is_active FROM eas.app_user WHERE username = %s",
                [username],
            )
            state = cursor.fetchone()
        if not state or not state[0]:
            print("[WARNING] Khong xac minh duoc co bat buoc doi mat khau; kiem tra database.")
        if state and not state[1]:
            print("[WARNING] Tai khoan van dang bi khoa. Can kich hoat qua quy trinh quan tri.")
    except Exception:
        print("[WARNING] Khong doc duoc trang thai sau reset. Kiem tra lai truoc khi dang nhap.")

    print("\n=== MAT KHAU TAM THOI (CHI HIEN THI MOT LAN) ===")
    print(password)
    print("===========================================")
    print("Dang nhap va DOI MAT KHAU NGAY khi duoc yeu cau.")
    print("Khong luu mat khau tam vao ma nguon, .env, ticket hoac chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
