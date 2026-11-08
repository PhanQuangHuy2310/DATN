"""Settings diagnostics must never print or embed private env values."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock

path = Path(__file__).resolve().parents[1] / "ai_service" / "check_config_local.py"
spec = importlib.util.spec_from_file_location("eas_ai_preflight", path)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightMessageTests(unittest.TestCase):
    def test_invalid_bool_and_int_fields_report_names_not_inputs(self):
        exception = Mock()
        exception.errors.return_value = [
            {"loc": ("ocr_use_gpu",), "type": "bool_parsing", "input": "secret"},
            {"loc": ("auto_approve_max_risk",), "type": "int_parsing", "input": "secret2"},
        ]
        message = " ".join(preflight.field_errors(exception))
        self.assertIn("ocr_use_gpu", message)
        self.assertIn("auto_approve_max_risk", message)
        self.assertNotIn("secret", message)
