"""Changing a request type's group must never leave it without a usable release."""

from django.test import SimpleTestCase

from api_core.administration.workflows import _switch_lifecycle
from api_core.workflow.errors import CommandError


class FakeCursor:
    def __init__(self, active_lifecycle, published_release=None):
        self.results = [(active_lifecycle,), published_release]
        self.updates = []

    def execute(self, sql, params):
        if sql.lstrip().upper().startswith("UPDATE"):
            self.updates.append((sql, params))

    def fetchone(self):
        return self.results.pop(0)


class SwitchLifecycleTests(SimpleTestCase):
    def test_moves_to_the_published_release_of_the_new_group(self):
        cur = FakeCursor("A", ("rel-b",))
        _switch_lifecycle(cur, "t1", "B")
        sql, params = cur.updates[0]
        self.assertIn("active_release_id", sql)
        self.assertEqual(params, ["B", "rel-b", "t1"])

    def test_refuses_when_the_new_group_has_no_published_release(self):
        cur = FakeCursor("A", None)
        with self.assertRaises(CommandError) as ctx:
            _switch_lifecycle(cur, "t1", "B")
        self.assertEqual(str(ctx.exception), "LIFECYCLE_RELEASE_REQUIRED")
        self.assertEqual(cur.updates, [])

    def test_types_without_a_release_just_change_group(self):
        cur = FakeCursor(None)
        _switch_lifecycle(cur, "t1", "C")
        self.assertEqual(cur.updates[0][1], ["C", "t1"])
