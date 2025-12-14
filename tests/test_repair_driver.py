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

    @patch('pandas.read_csv')
    @patch('repair_pipeline.repair_driver.FixApplier')
    @patch('repair_pipeline.repair_driver.TerraformValidator')
    @patch('repair_pipeline.repair_driver.DiagnosticsExtractor')
    @patch('repair_pipeline.repair_driver.DiagnosticsWriter')
    def test_evaluate_repairs_block(self, mock_writer, mock_extractor, mock_validator, mock_applier, mock_read_csv):
        # Setup mock data for block repair
        mock_df = pd.DataFrame({
            "filename": ["clones/proj1/main.tf"],
            "fixed_block_content": ["fixed block"],
            "line_start": [10],
            "line_end": [15],
            "project_name": ["proj1"],
            "oid": ["123"],
            "iteration_id": [1],
            "severity": ["high"],
            "summary": ["sum"],
            "detail": ["det"],
            "working_directory": ["wd"],
            "llm_name": ["gpt"],
            "prompt_content": ["p"],
            "raw_llm_output": ["raw"],
            "explanation": ["exp"]
        })
        mock_read_csv.return_value = mock_df

        mock_applier.apply_fix.return_value = "main.tf.bak"
        mock_validator.validate.return_value = {"valid": True}
        mock_extractor.extract_rows.return_value = []

        evaluator = RepairEvaluator(clones_root="clones")
        evaluator.evaluate_repairs("fixes.csv")

        # Verify interactions
        # Expected path: clones_root + filename (minus clones/) -> clones/proj1/main.tf
        # Wait, logic is: relative_path = row["filename"] (clones/proj1/main.tf)
        # if startswith clones/: relative_path = proj1/main.tf
        # original_file = os.path.join(clones_root, relative_path) -> clones/proj1/main.tf
        expected_file = "clones/proj1/main.tf"
        # On windows separator might differ but we mock os.path.join partially or rely on unix style in test if os is mocked or just valid path
        # The test environment is windows, so os.path.join will use backslashes. 
        # But let's assume standard behavior.
        
        # We need to match what the code does. 
        # The code separates checks.
        
        mock_applier.apply_fix.assert_called_with(os.path.normpath(expected_file), "fixed block", start_line=10, end_line=15)
        mock_writer.write_rows.assert_called()
        mock_applier.restore_original.assert_called()


    @patch("repair_pipeline.repair_driver.pd.read_csv")
    @patch("repair_pipeline.repair_driver.FixApplier.apply_fix")
    @patch("repair_pipeline.repair_driver.TerraformValidator")
    @patch("repair_pipeline.repair_driver.DiagnosticsExtractor")
    @patch("repair_pipeline.repair_driver.DiagnosticsWriter")
    def test_evaluate_repairs_with_problems_mapping(self, MockWriter, MockExtractor, MockValidator, MockApplier, MockReadVal):
        """
        Verify that if problems_dataset is provided, we use coordinates from PROBLEMS csv
        mapped via OID.
        """
        # Mock problems DF
        problems_df = pd.DataFrame([{
            "oid": "test-oid-123", # Key for mapping
            "impacted_block_start_line": 5,
            "impacted_block_end_line": 10
        }])
        
        # Mock fixes DF
        fixes_df = pd.DataFrame([{
            "iteration_id": 1,
            "project_name": "proj1",
            "oid": "test-oid-123", # Matching key
            "filename": "clones/proj1/main.tf",
            "line_start": 2, 
            "line_end": 2,
            "fixed_block_content": "resource \"foo\" \"bar\" {}",
            "raw_llm_output": "...",
            "explanation": "..."
        }])
        
        def side_effect_read_csv(filepath, *args, **kwargs):
            if not isinstance(filepath, str):
                 return fixes_df
            if "problems.csv" in filepath:
                return problems_df
            return fixes_df
            
        MockReadVal.side_effect = side_effect_read_csv
        
        with patch("os.path.exists") as MockExists:
            MockExists.return_value = True
            
            evaluator = RepairEvaluator(
                output_csv="out.csv", 
                outcomes_csv="outcome.csv", 
                clones_root="clones",
                repair_mode="block",
                problems_dataset="problems.csv"
            )
            
            MockValidator.validate.return_value = {}
            MockExtractor.extract_rows.return_value = []
            
            evaluator.evaluate_repairs("fixes.csv")
            
            # Verify usage
            MockApplier.apply_fix.assert_called()
            args, kwargs = MockApplier.apply_fix.call_args
            
            # Should use 5 and 10 from problems_df via OID mapping
            self.assertEqual(kwargs['start_line'], 5)
            self.assertEqual(kwargs['end_line'], 10)


if __name__ == '__main__':
    unittest.main()
