import unittest
from unittest.mock import patch
from terraform_validation.writer import DiagnosticsWriter


class TestDiagnosticsWriter(unittest.TestCase):

    def test_compute_oid(self):
        row = {
            "filename": "main.tf",
            "line_start": 1,
            "line_end": 10
        }
        oid = DiagnosticsWriter.compute_oid(row)
        self.assertIsInstance(oid, str)
        self.assertTrue(len(oid) > 0)

    @patch('pandas.DataFrame.to_csv')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_write_rows(self, mock_getsize, mock_exists, mock_to_csv):
        mock_exists.return_value = True
        mock_getsize.return_value = 100  # File not empty

        rows = [{
            "project_name": "p1",
            "working_directory": ".",
            "severity": "error",
            "summary": "sum",
            "detail": "det",
            "filename": "f.tf",
            "line_start": 1,
            "col_start": 1,
            "line_end": 2,
            "col_end": 2,
            "file_content": "content"
        }]

        DiagnosticsWriter.write_rows(rows, "out.csv")

        mock_to_csv.assert_called_once()
        # Verify header=False because file exists and is not empty
        args, kwargs = mock_to_csv.call_args
        self.assertFalse(kwargs['header'])


if __name__ == '__main__':
    unittest.main()
