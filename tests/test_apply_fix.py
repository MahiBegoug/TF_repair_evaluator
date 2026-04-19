import os
import tempfile
import unittest

from repair_pipeline.apply_fix import FixApplier


class TestFixApplier(unittest.TestCase):

    def test_apply_fix_full_replacement_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = os.path.join(tmpdir, "module")
            os.makedirs(module_dir, exist_ok=True)
            original_file = os.path.join(module_dir, "main.tf")

            with open(original_file, "w", encoding="utf-8") as f:
                f.write('resource "aws_instance" "old" {}\n')

            backup_path = FixApplier.apply_fix(original_file, 'resource "aws_instance" "new" {}')

            self.assertTrue(os.path.exists(original_file))
            self.assertTrue(os.path.exists(backup_path))
            self.assertNotEqual(os.path.dirname(backup_path), module_dir)

            with open(original_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), 'resource "aws_instance" "new" {}\n')

            FixApplier.restore_original(original_file, backup_path)

            with open(original_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), 'resource "aws_instance" "old" {}\n')
            self.assertFalse(os.path.exists(backup_path))

    def test_apply_fix_partial_replacement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = os.path.join(tmpdir, "module")
            os.makedirs(module_dir, exist_ok=True)
            original_file = os.path.join(module_dir, "main.tf")

            with open(original_file, "w", encoding="utf-8") as f:
                f.write("line1\nline2\nline3\nline4\nline5")

            backup_path = FixApplier.apply_fix(original_file, "new_line", start_line=2, end_line=4)

            with open(original_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "line1\nnew_line\nline5")

            FixApplier.restore_original(original_file, backup_path)

    def test_apply_fix_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            FixApplier.apply_fix("missing.tf", "content")

    def test_restore_pending_backups_restores_registered_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            module_dir = os.path.join(tmpdir, "module")
            os.makedirs(module_dir, exist_ok=True)
            original_file = os.path.join(module_dir, "main.tf")

            with open(original_file, "w", encoding="utf-8") as f:
                f.write('resource "aws_instance" "old" {}\n')

            backup_path = FixApplier.apply_fix(original_file, 'resource "aws_instance" "new" {}')
            restored = FixApplier.restore_pending_backups(reason="test cleanup")

            self.assertEqual(restored, 1)
            self.assertFalse(os.path.exists(backup_path))

            with open(original_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), 'resource "aws_instance" "old" {}\n')


if __name__ == "__main__":
    unittest.main()
