import unittest
from unittest.mock import patch, mock_open
from terraform_validation.extractor import DiagnosticsExtractor


class TestDiagnosticsExtractor(unittest.TestCase):

    @patch('os.walk')
    @patch('builtins.open', new_callable=mock_open, read_data="resource \"aws_instance\" \"x\" {}")
    def test_load_tf_files(self, mock_file, mock_walk):
        mock_walk.return_value = [
            ("root", [], ["main.tf", "other.txt"])
        ]

        cache = DiagnosticsExtractor.load_tf_files("root")

        self.assertIn("root\\main.tf", cache)
        self.assertNotIn("root\\other.txt", cache)

    def test_normalize(self):
        self.assertEqual(DiagnosticsExtractor.normalize(None), [])
        self.assertEqual(DiagnosticsExtractor.normalize({"key": "val"}), [{"key": "val"}])
        self.assertEqual(DiagnosticsExtractor.normalize([{"a": 1}, "invalid"]), [{"a": 1}])

    @patch('terraform_validation.extractor.DiagnosticsExtractor.load_tf_files')
    def test_extract_rows(self, mock_load):
        import os
        # Use os.path.join to match the key expected by the code under test
        key = os.path.join("/abs/path", "main.tf")
        mock_load.return_value = {key: "content"}

        result = {
            "path": "/abs/path",
            "diagnostics": [{
                "severity": "error",
                "summary": "Syntax error",
                "range": {
                    "filename": "main.tf",
                    "start": {"line": 1, "column": 1},
                    "end": {"line": 1, "column": 10}
                }
            }]
        }

        rows = DiagnosticsExtractor.extract_rows("proj1", result, "/abs/path")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project_name"], "proj1")
        self.assertEqual(rows[0]["severity"], "error")
        self.assertIn("content", rows[0]["file_content"])


if __name__ == '__main__':
    unittest.main()
