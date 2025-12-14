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
            # Full file replacement checks
            mock_file().write.assert_called_once_with(fixed_content)

    @patch('os.path.exists')
    @patch('os.path.abspath')
    @patch('shutil.copyfile')
    def test_apply_fix_partial(self, mock_copyfile, mock_abspath, mock_exists):
        mock_abspath.side_effect = lambda x: x
        mock_exists.return_value = True

        original_file = "test.tf"
        # Original content has 5 lines
        original_content = "line1\nline2\nline3\nline4\nline5"
        
        # We replace lines 2-4 (indices 1-4) with "new_line\n"
        # start_line=2, end_line=4
        # Expected result: "line1\n" + "new_line\n" + "line5"
        
        fixed_block = "new_line" 

        with patch("builtins.open", mock_open(read_data=original_content)) as mock_file:
            # mock_open doesn't implement readlines well for iteration usually, but readlines() is standard.
            # We need to manually set return value of readlines if we want robust test or trust mock_open implementation in this environment.
            # Standard mock_open doesn't automatically split read_data on readlines call in older python versions, let's explicit it.
            mock_file.return_value.readlines.return_value = ["line1\n", "line2\n", "line3\n", "line4\n", "line5"]

            backup_path = FixApplier.apply_fix(original_file, fixed_block, start_line=2, end_line=4)

            mock_file.assert_called_with("test.tf", "w", encoding="utf-8")
            
            # Reconstruct expected write
            # lines[:1] -> ["line1\n"]
            # lines[4:] -> ["line5"]
            # "line1\n" + "new_line\n" + "line5"
            expected_content = "line1\nnew_line\nline5"
            
            mock_file().write.assert_called_once_with(expected_content)

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
