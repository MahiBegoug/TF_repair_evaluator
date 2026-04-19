import os
import tempfile
import unittest

from repair_pipeline.clone_lock import CloneTreeLock


class TestCloneTreeLock(unittest.TestCase):

    def test_acquire_and_release_creates_lock_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock = CloneTreeLock(tmpdir)

            with lock:
                self.assertTrue(os.path.exists(lock.lock_path))
                lock._fh.seek(0)
                content = lock._fh.read()
                self.assertIn("pid=", content)
                self.assertIn("clones_root=", content)

            self.assertIsNone(lock._fh)


if __name__ == "__main__":
    unittest.main()
