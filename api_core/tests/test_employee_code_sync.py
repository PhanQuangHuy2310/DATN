"""Item 4.5: attendance matches HRM employee codes first, email as fallback."""

from django.test import SimpleTestCase

from api_core.management.commands.sync_employee_codes import (
    match_employees,
    normalize_name,
)
from api_core.workflow.service import SQL_ATTENDANCE_MATCH


class EmployeeCodeMatchingTests(SimpleTestCase):
    def test_email_first_then_unique_name(self):
        accounts = [
            ("a1", "an.nguyen@eas.com", "Nguyễn Minh An"),
            ("a2", "ngoc.tran@eas.com", "Trần Thị Bích Ngọc"),
            ("a3", "x@eas.com", "Không Có Trong HRM"),
        ]
        employees = [
            ("E1", "an.nguyen@eas.com", "Nguyen Minh An"),
            ("E2", "ngoc.tran@example.test", "TRẦN THỊ BÍCH NGỌC"),
            ("E3", "other@example.test", "Người Khác"),
        ]
        matches, unmatched, unused, ambiguous = match_employees(accounts, employees)
        self.assertEqual(matches, {"a1": ("E1", "email"), "a2": ("E2", "name")})
        self.assertEqual([a[0] for a in unmatched], ["a3"])
        self.assertEqual(unused, ["E3"])
        self.assertEqual(ambiguous, [])

    def test_duplicate_names_are_reported_not_guessed(self):
        accounts = [("a1", "x@eas.com", "Lê Văn Hải")]
        employees = [
            ("E1", "h1@example.test", "Lê Văn Hải"),
            ("E2", "h2@example.test", "Le Van Hai"),
        ]
        matches, unmatched, _, ambiguous = match_employees(accounts, employees)
        self.assertEqual(matches, {})
        self.assertEqual(ambiguous, ["Lê Văn Hải"])
        self.assertEqual(len(unmatched), 1)

    def test_vietnamese_names_normalize(self):
        self.assertEqual(normalize_name("  Đặng   Quốc Tuấn "), "dang quoc tuan")


class AttendanceMatchSqlTests(SimpleTestCase):
    def test_code_wins_and_email_is_fallback(self):
        sql = " ".join(SQL_ATTENDANCE_MATCH.split())
        self.assertIn(
            "THEN to_jsonb(a)->>'employee_code' = to_jsonb(u)->>'employee_code'", sql
        )
        self.assertIn("ELSE a.employee_email = u.email", sql)
