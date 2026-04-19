import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from repair_pipeline.repair_driver import RepairEvaluator


class TestRepairEvaluatorSafety(unittest.TestCase):

    @patch("repair_pipeline.repair_driver.os.path.exists", return_value=False)
    @patch("repair_pipeline.repair_driver.pd.DataFrame.to_csv")
    @patch("repair_pipeline.repair_driver.ErrorCategorizer")
    @patch("repair_pipeline.repair_driver.ValidationService")
    @patch("repair_pipeline.repair_driver.MetricsCalculator")
    @patch("repair_pipeline.repair_driver.FileCoordinateResolver")
    @patch("repair_pipeline.repair_driver.ErrorMatchingService")
    @patch("repair_pipeline.repair_driver.FixApplier.restore_original")
    @patch("repair_pipeline.repair_driver.FixApplier.apply_fix", return_value="backup.tf")
    def test_serial_evaluation_restores_file_after_failure(
        self,
        mock_apply_fix,
        mock_restore_original,
        _mock_error_matcher,
        _mock_file_resolver,
        _mock_metrics,
        _mock_validation_service,
        _mock_error_categorizer,
        _mock_to_csv,
        _mock_exists,
    ):
        evaluator = RepairEvaluator(output_csv="out.csv", outcomes_csv="outcomes.csv")
        evaluator._extract_project_name = MagicMock(return_value="proj")
        evaluator._get_original_file_path = MagicMock(return_value="/tmp/main.tf")
        evaluator._get_fix_content_and_coordinates = MagicMock(return_value=("fixed", 1, 1))
        evaluator._get_baseline_errors = MagicMock(return_value=[])
        evaluator._apply_and_validate = MagicMock(side_effect=RuntimeError("boom"))

        df = pd.DataFrame([{
            "specific_oid": "abc123",
            "oid": "oid123",
            "filename": "clones/proj/main.tf",
            "iteration_id": 1,
        }])

        evaluator.evaluate_repairs_serial(df)

        mock_apply_fix.assert_called_once()
        mock_restore_original.assert_called_once_with("/tmp/main.tf", "backup.tf")


if __name__ == "__main__":
    unittest.main()
