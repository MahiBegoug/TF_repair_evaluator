import unittest
from unittest.mock import patch, mock_open
from terraform_validation.extractor import DiagnosticsExtractor


class TestDiagnosticsExtractor(unittest.TestCase):

    @patch('os.walk')
    @patch('builtins.open', new_callable=mock_open, read_data="resource \"aws_instance\" \"x\" {}")
    def test_load_tf_files(self, mock_file, mock_walk):
        import os
        mock_walk.return_value = [
            ("root", [], ["main.tf", "other.txt"])
        ]

        cache = DiagnosticsExtractor.load_tf_files("root")

        expected_key = os.path.abspath(os.path.join("root", "main.tf")).replace("\\", "/")
        self.assertIn(expected_key, cache)
        self.assertNotIn("root\\other.txt", cache)

    def test_normalize(self):
        self.assertEqual(DiagnosticsExtractor.normalize(None), [])
        self.assertEqual(DiagnosticsExtractor.normalize({"key": "val"}), [{"key": "val"}])
        self.assertEqual(DiagnosticsExtractor.normalize([{"a": 1}, "invalid"]), [{"a": 1}])

    def test_compute_specific_oid_collapses_whitespace(self):
        base = {
            "filename": "clones/org__repo/main.tf",
            "line_start": 10,
            "line_end": 10,
            "summary": "Unsupported argument",
            "detail": "An argument named \"x\" is not expected here.",
        }
        variant = {
            **base,
            # Add newlines and extra spaces; should hash identically.
            "detail": "An argument named  \"x\"\n\nis not expected here.",
        }
        self.assertEqual(
            DiagnosticsExtractor.compute_specific_oid(base),
            DiagnosticsExtractor.compute_specific_oid(variant),
        )

    @patch('terraform_validation.extractor.DiagnosticsExtractor.load_tf_files')
    def test_extract_rows(self, mock_load):
        import os
        # Match the exact absolute-path key format used by DiagnosticsExtractor.load_tf_files.
        abs_key = os.path.abspath(os.path.join("/abs/path", "main.tf")).replace("\\", "/")
        mock_load.return_value = {abs_key: "content"}

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
