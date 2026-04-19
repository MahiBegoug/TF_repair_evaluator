import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from terraform_validation.validator import TerraformValidator


class TestTerraformValidator(unittest.TestCase):

    @patch("subprocess.run")
    def test_validate_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "valid": True,
            "diagnostics": [],
        })
        mock_run.return_value = mock_proc

        result = TerraformValidator.validate("path/to/module", timeout_seconds=30)

        self.assertTrue(result["validate_success"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["diagnostics"], [])
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_validate_json_error(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Invalid JSON"
        mock_run.return_value = mock_proc

        result = TerraformValidator.validate("path/to/module")

        self.assertTrue(result["validate_success"])
        self.assertFalse(result["timed_out"])
        self.assertIsNone(result["validate_json"])

    @patch("subprocess.run")
    def test_validate_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["terraform", "validate", "-no-color", "-json"],
            timeout=12,
            output='{"diagnostics": [{"summary": "timeout warning"}]}',
        )

        result = TerraformValidator.validate("path/to/module", timeout_seconds=12)

        self.assertFalse(result["validate_success"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(len(result["diagnostics"]), 1)


if __name__ == "__main__":
    unittest.main()
