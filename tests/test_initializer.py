import unittest
from unittest.mock import patch, MagicMock
from terraform_validation.initializer import TerraformInitializer


class TestTerraformInitializer(unittest.TestCase):

    @patch('subprocess.run')
    def test_init_module_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        result = TerraformInitializer.init_module("path/to/module")

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_init_module_failure(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Error initializing"
        mock_run.return_value = mock_proc

        result = TerraformInitializer.init_module("path/to/module")

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
