import unittest
import pandas as pd
from unittest.mock import patch
from repair_pipeline.repair_driver import RepairEvaluator


class TestRepairEvaluator(unittest.TestCase):

    @patch('os.path.exists')
    @patch('pandas.DataFrame.to_csv')
    def test_init_creates_csv_if_missing(self, mock_to_csv, mock_exists):
        mock_exists.return_value = False
        RepairEvaluator(output_csv="new_results.csv")
        mock_to_csv.assert_called_once()

    @patch('os.path.exists')
    @patch('pandas.DataFrame.to_csv')
    def test_init_does_not_create_csv_if_exists(self, mock_to_csv, mock_exists):
        mock_exists.return_value = True
        RepairEvaluator(output_csv="existing_results.csv")
        mock_to_csv.assert_not_called()

    @patch('pandas.read_csv')
    @patch('repair_pipeline.repair_driver.FixApplier')
    @patch('repair_pipeline.repair_driver.TerraformValidator')
    @patch('repair_pipeline.repair_driver.DiagnosticsExtractor')
    @patch('repair_pipeline.repair_driver.DiagnosticsWriter')
    def test_evaluate_repairs(self, mock_writer, mock_extractor, mock_validator, mock_applier, mock_read_csv):
        # Setup mock data
        mock_df = pd.DataFrame({
            "filename": ["main.tf"],
            "fixed_file": ["fixed content"],
            "project_name": ["proj1"]
        })
        mock_read_csv.return_value = mock_df

        mock_applier.apply_fix.return_value = "main.tf.bak"
        mock_validator.validate.return_value = {"valid": True}
        mock_extractor.extract_rows.return_value = [{"diag": 1}]

        evaluator = RepairEvaluator()
        evaluator.evaluate_repairs("fixes.csv")

        # Verify interactions
        mock_applier.apply_fix.assert_called_with("main.tf", "fixed content")
        mock_validator.validate.assert_called()
        mock_extractor.extract_rows.assert_called()
        mock_writer.write_rows.assert_called_with([{"diag": 1}], "repair_eval_diagnostics.csv")
        mock_applier.restore_original.assert_called_with("main.tf", "main.tf.bak")


if __name__ == '__main__':
    unittest.main()
