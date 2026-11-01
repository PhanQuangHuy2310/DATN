"""Copy HRM employee codes (mock_hr.employee_directory) onto eas.app_user.

Match order: exact work email, then unique normalized full name. Accounts and
employees that do not match are reported, never guessed. Dry run by default;
--apply writes eas.app_user.employee_code (migration 16 required).
"""

from __future__ import annotations

import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "").replace("đ", "d").replace("Đ", "D")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


def match_employees(accounts, employees):
    """accounts: [(id, email, name)], employees: [(code, email, name)].

    Returns (matches {account_id: (code, how)}, unmatched_accounts, unmatched_codes, ambiguous).
    """
    by_email = {(e[1] or "").lower(): e for e in employees}
    by_name: dict[str, list] = {}
    for employee in employees:
        by_name.setdefault(normalize_name(employee[2]), []).append(employee)
    matches, used, ambiguous = {}, set(), []
    for account_id, email, name in accounts:
        employee = by_email.get((email or "").lower())
        how = "email"
        if employee is None:
            candidates = by_name.get(normalize_name(name), [])
            if len(candidates) > 1:
                ambiguous.append(name)
                continue
            employee = candidates[0] if candidates else None
            how = "name"
        if employee is None or employee[0] in used:
            continue
        used.add(employee[0])
        matches[account_id] = (employee[0], how)
    unmatched_accounts = [a for a in accounts if a[0] not in matches]
    unmatched_codes = [e[0] for e in employees if e[0] not in used]
    return matches, unmatched_accounts, unmatched_codes, ambiguous


class Command(BaseCommand):
    help = "Sync HRM employee codes onto accounts and report unmatched records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the matches.")

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id::text, email, display_name FROM eas.app_user
                WHERE is_active
                  AND NOT COALESCE((to_jsonb(app_user)->>'is_system_account')::boolean, false)
                ORDER BY email
                """
            )
            accounts = cursor.fetchall()
            cursor.execute(
                "SELECT employee_code, work_email, display_name FROM mock_hr.employee_directory"
            )
            employees = cursor.fetchall()
        matches, unmatched_accounts, unmatched_codes, ambiguous = match_employees(
            accounts, employees
        )
        by_how = {"email": 0, "name": 0}
        for _code, how in matches.values():
            by_how[how] += 1
        self.stdout.write(
            f"Accounts: {len(accounts)} | HRM employees: {len(employees)} | "
            f"matched: {len(matches)} (email {by_how['email']}, name {by_how['name']}) | "
            f"unmatched accounts: {len(unmatched_accounts)} | "
            f"unmatched HRM employees: {len(unmatched_codes)} | ambiguous names: {len(ambiguous)}"
        )
        for _id, email, name in unmatched_accounts:
            self.stdout.write(f"  - no HRM match: {email} ({name})")
        if not options["apply"]:
            self.stdout.write("Dry run: nothing written. Use --apply to save.")
            return
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='eas' AND table_name='app_user' AND column_name='employee_code'
                """
            )
            if not cursor.fetchone():
                raise CommandError(
                    "Run database/migrations/16_employee_code.sql first."
                )
            for account_id, (code, _how) in matches.items():
                cursor.execute(
                    "UPDATE eas.app_user SET employee_code=%s WHERE id=%s",
                    [code, account_id],
                )
        self.stdout.write(f"Saved {len(matches)} employee codes.")
