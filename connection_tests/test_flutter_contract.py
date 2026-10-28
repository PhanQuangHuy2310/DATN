"""Static contract smoke tests while Flutter SDK is unavailable."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FlutterContractTests(unittest.TestCase):
    def test_temp_password_login_does_not_call_forbidden_me(self):
        source = (ROOT / 'mobile_app/lib/eas_api.dart').read_text(encoding='utf-8')
        self.assertIn("loginUser['must_change_password'] == true", source)
        self.assertIn('return loginUser;', source)
        self.assertIn('return me();', source)
        self.assertIn("'/api/v1/auth/password'", source)

    def test_mobile_decisions_preserve_null_reason_and_security(self):
        source = (ROOT / 'mobile_app/lib/eas_api.dart').read_text(encoding='utf-8')
        self.assertIn("'reason': action == 'APPROVE' ? null : reason", source)
        self.assertIn("'reason': action == 'ACCEPT' ? null : reason", source)
        self.assertIn("'Idempotency-Key'", source)
        self.assertIn("'X-CSRFToken'", source)
        self.assertIn("base.scheme != 'https'", source)

if __name__ == '__main__':
    unittest.main()
