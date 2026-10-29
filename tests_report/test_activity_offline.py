"""Pure Python and source-contract checks runnable without Django installed."""
from pathlib import Path
import unittest
from api_core.workflow.activity import activity_label, is_notifiable_action

ROOT = Path(__file__).resolve().parents[1]

class ActivityOfflineTests(unittest.TestCase):
    def test_read_operations_are_not_notified(self):
        self.assertFalse(is_notifiable_action("ATTACHMENT_DOWNLOADED"))
        self.assertFalse(is_notifiable_action("AUDIT_VERIFIED"))

    def test_user_actions_have_explicit_labels(self):
        for action in ("DRAFT_CREATED", "REQUEST_SUBMITTED", "APPROVAL_REJECT",
                       "EXECUTION_STARTED", "ACCEPTANCE_ACCEPT", "REQUEST_CANCELLED"):
            self.assertTrue(is_notifiable_action(action))
            self.assertNotEqual(activity_label(action), "Hồ sơ có hoạt động mới")

    def test_db07_initial_draft_never_passes_null_payload(self):
        src = (ROOT / "api_core/workflow/service.py").read_text(encoding="utf8")
        self.assertIn("Jsonb(draft_payload or {})", src)
        self.assertNotIn("Jsonb(draft_payload) if draft_payload else None", src)

    def test_notification_is_written_with_audit_transaction(self):
        src = (ROOT / "api_core/workflow/service.py").read_text(encoding="utf8")
        self.assertIn("if is_notifiable_action(action)", src)
        self.assertIn("INSERT INTO eas.outbox_event(request_id,event_type,payload,dedupe_key)", src)
        worker = (ROOT / "api_core/worker.py").read_text(encoding="utf8")
        self.assertIn('item.event_type == "REQUEST_ACTIVITY"', worker)
        self.assertIn("p.read_revoked_at IS NULL", worker)

if __name__ == "__main__":
    unittest.main()
