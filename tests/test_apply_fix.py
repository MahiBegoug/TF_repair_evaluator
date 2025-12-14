import unittest
from unittest.mock import patch, mock_open
from repair_pipeline.apply_fix import FixApplier


class TestFixApplier(unittest.TestCase):

    @patch('os.path.exists')
    @patch('os.path.abspath')
    @patch('shutil.copyfile')
    def test_apply_fix_success(self, mock_copyfile, mock_abspath, mock_exists):
        mock_abspath.side_effect = lambda x: x
        mock_exists.return_value = True

        original_file = "test.tf"
        fixed_content = "resource \"aws_instance\" \"test\" {}"

        with patch("builtins.open", mock_open()) as mock_file:
            backup_path = FixApplier.apply_fix(original_file, fixed_content)

            self.assertEqual(backup_path, "test.tf.bak")
            mock_copyfile.assert_called_once_with("test.tf", "test.tf.bak")
            mock_file.assert_called_once_with("test.tf", "w", encoding="utf-8")
            mock_file().write.assert_called_once_with(fixed_content)

    @patch('os.path.exists')
    @patch('os.path.abspath')
    def test_apply_fix_file_not_found(self, mock_abspath, mock_exists):
        mock_abspath.side_effect = lambda x: x
        mock_exists.return_value = False

        with self.assertRaises(FileNotFoundError):
            FixApplier.apply_fix("missing.tf", "content")

    @patch('os.path.exists')
    @patch('os.path.abspath')
    @patch('shutil.move')
    def test_restore_original_success(self, mock_move, mock_abspath, mock_exists):
        mock_abspath.side_effect = lambda x: x
        mock_exists.return_value = True

        FixApplier.restore_original("test.tf", "test.tf.bak")

        mock_move.assert_called_once_with("test.tf.bak", "test.tf")

    @patch('os.path.exists')
    @patch('os.path.abspath')
    @patch('shutil.move')
    def test_restore_original_no_backup(self, mock_move, mock_abspath, mock_exists):
        mock_abspath.side_effect = lambda x: x
        mock_exists.return_value = False

        FixApplier.restore_original("test.tf", "test.tf.bak")

        mock_move.assert_not_called()


if __name__ == '__main__':
    unittest.main()
