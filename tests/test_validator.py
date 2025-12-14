import unittest
import json
from unittest.mock import patch, MagicMock
from terraform_validation.validator import TerraformValidator


class TestTerraformValidator(unittest.TestCase):

    @patch('subprocess.run')
    def test_validate_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "valid": True,
            "diagnostics": []
        })
        mock_run.return_value = mock_proc

        result = TerraformValidator.validate("path/to/module")

        self.assertTrue(result["validate_success"])
        self.assertEqual(result["diagnostics"], [])

    @patch('subprocess.run')
    def test_validate_json_error(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Invalid JSON"
        mock_run.return_value = mock_proc

        result = TerraformValidator.validate("path/to/module")

        self.assertTrue(result["validate_success"])  # Command succeeded, but parsing failed
        self.assertIsNone(result["validate_json"])


if __name__ == '__main__':
    unittest.main()
