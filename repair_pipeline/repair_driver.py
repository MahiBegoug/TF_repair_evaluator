# repair_driver.py
import os
import json
import pandas as pd

from repair_pipeline.apply_fix import FixApplier
from repair_pipeline.error_categorizer import ErrorCategorizer
from repair_pipeline.error_matcher import ErrorMatchingService
from repair_pipeline.file_resolver import FileCoordinateResolver
from repair_pipeline.metrics_calculator import MetricsCalculator
from repair_pipeline.validation_service import ValidationService
from terraform_validation.writer import DiagnosticsWriter


class RepairEvaluator:

    def __init__(self, output_csv="repair_eval_diagnostics.csv", outcomes_csv="repair_outcomes.csv",
                 clones_root="clones", repair_mode="auto", problems_dataset=None, clear_existing=False):
        """
        This CSV will contain the diagnostics AFTER each LLM repair.
        And will follow the EXACT SAME format as DiagnosticsWriter.
        
        Args:
            output_csv: Path to diagnostics CSV file
            outcomes_csv: Path to outcomes/results CSV file
            clones_root: Root directory for cloned repositories
            repair_mode: "auto", "block", or "file"
            problems_dataset: Path to problems CSV (optional)
            clear_existing: If True, DELETE existing CSV files before starting (fresh run)
        """
        self.output_csv = output_csv
        self.clones_root = clones_root
        self.repair_mode = repair_mode
        self.problems = pd.read_csv(problems_dataset) if problems_dataset and os.path.exists(problems_dataset) else None
        self.error_matcher = ErrorMatchingService(line_tolerance=3)
        self.file_resolver = FileCoordinateResolver(clones_root=clones_root, problems_dataset=self.problems)
        self.metrics_calculator = MetricsCalculator(clones_root=clones_root, error_matcher=self.error_matcher, problems_dataset=self.problems)
        self.validation_service = ValidationService(clones_root=clones_root, output_csv=output_csv)
        self.error_categorizer = ErrorCategorizer(clones_root=clones_root, problems_dataset=self.problems, output_csv=output_csv)

        # Clear existing CSV files if requested (fresh start)
        if clear_existing:
            if os.path.exists(output_csv):
                os.remove(output_csv)
                print(f"[CLEAR] ✓ Deleted old diagnostics: {output_csv}")
            if os.path.exists(outcomes_csv):
                os.remove(outcomes_csv)
                print(f"[CLEAR] ✓ Deleted old outcomes: {outcomes_csv}")

        # Create empty CSV with headers if doesn't exist
        if not os.path.exists(output_csv):
            pd.DataFrame([], columns=DiagnosticsWriter.COLUMNS) \
                .to_csv(output_csv, index=False)

        self.outcomes_csv = outcomes_csv
        if not os.path.exists(self.outcomes_csv):
            pd.DataFrame([], columns=[
                "oid", "iteration_id", "llm_name", "filename",
                "line_is_clean", "line_specific_error_fixed", 
                "module_total_errors", "file_errors", "module_errors",
                "module_original_errors_remaining", "module_fix_introduced_errors"
            ]).to_csv(self.outcomes_csv, index=False)

    
    def _extract_project_name(self, row):
        """Extract project name from row - delegates to file_resolver."""
        return self.file_resolver.extract_project_name(row)
    
    def _get_original_file_path(self, filename):
        """Convert relative filename to absolute path - delegates to file_resolver."""
        return self.file_resolver.get_original_file_path(filename)
    
    def _get_block_coordinates_from_problems(self, oid):
        """Get block coordinates from problems dataset - delegates to file_resolver."""
        return self.file_resolver.get_block_coordinates_from_problems(oid)
    
    def _get_fix_content_and_coordinates(self, row):
        """Extract fix content and coordinates - delegates to file_resolver."""
        return self.file_resolver.get_fix_content_and_coordinates(row, self.repair_mode)
    
    def _apply_and_validate(self, original_file, project, fixed_content, start_line, end_line, iteration_id, baseline_errors=None, original_problem_oid=None):
        """Apply fix, run terraform validate, and extract diagnostics with error categorization."""
        
        # Use ValidationService to run validation and extract diagnostics
        # Don't write to CSV yet - wait for error categorization!
        extracted_rows = self.validation_service.validate_and_extract(
            original_file=original_file,
            project=project,
            iteration_id=iteration_id,
            original_problem_oid=original_problem_oid,
            write_to_csv=False
        )
        
        # Categorize errors using ErrorCategorizer
        if baseline_errors is not None or self.problems is not None:
            extracted_rows = self.error_categorizer.categorize_errors(
                extracted_rows,
                original_file,
                iteration_id,
                baseline_errors=baseline_errors,
                original_problem_oid=original_problem_oid
            )
        else:
            # No baseline provided - mark as unknown
            for error in extracted_rows:
                error['is_original_error'] = None
                error['is_new_error'] = None
                error['is_new_to_dataset'] = None
                error['introduced_in_this_iteration'] = None
                error['first_seen_in'] = None
                error['exists_in_iterations'] = ''
        
        # Write enriched diagnostics to CSV
        if self.output_csv and extracted_rows:
            DiagnosticsWriter.write_rows(
                extracted_rows, 
                self.output_csv, 
                iteration_id=iteration_id, 
                original_problem_oid=original_problem_oid
            )

        return extracted_rows
    
    def _get_baseline_errors(self, original_file, project):
        """Get baseline errors - delegates to error_categorizer."""
        return self.error_categorizer.get_baseline_errors(original_file, project)
    
    def _get_existing_experiment_errors(self, filename, current_iteration_id):
        """Get experiment errors - delegates to error_categorizer."""
        return self.error_categorizer.get_existing_experiment_errors(filename, current_iteration_id)

    def _calculate_error_metrics(self, extracted_rows, original_file, baseline_errors=None):
        """Calculate error counts - delegates to metrics_calculator."""
        return self.metrics_calculator.calculate_error_metrics(extracted_rows, original_file, baseline_errors)
    
    def _evaluate_resolution_metrics(self, row, extracted_rows, start_line, end_line, fixed_file_content):
        """Evaluate whether the original error was resolved - delegates to metrics_calculator."""
        return self.metrics_calculator.evaluate_resolution_metrics(row, extracted_rows, start_line, end_line, fixed_file_content)
    
    def _create_outcome_row(self, row, original_file, resolution_metrics, error_counts):
        """Create outcome row for CSV - delegates to metrics_calculator."""
        return self.metrics_calculator.create_outcome_row(row, original_file, resolution_metrics, error_counts)
    
    def evaluate_repairs(self, llm_fixes_csv: str):
        df = pd.read_csv(llm_fixes_csv)

        for _, row in df.iterrows():
            # Extract project name
            project = self._extract_project_name(row)
            if not project:
                print(f"Skipping row, cannot determine project name: {row['filename']}")
                continue
            
            # Get file paths
            original_file = self._get_original_file_path(row["filename"])
            print(f"\n[PROCESSING] Processing fix for: {original_file}")
            
            # Get fix content and coordinates
            fixed_file_content, start_line, end_line = self._get_fix_content_and_coordinates(row)

            if fixed_file_content is None or pd.isna(fixed_file_content):
                print(f"Skipping row, no fixed content found for: {original_file} (Mode: {self.repair_mode})")
                continue
            
            # BASELINE: Capture errors from original file
            # Caching is handled internally by ErrorCategorizer
            baseline_errors = self._get_baseline_errors(original_file, project)

            backup_path = FixApplier.apply_fix(
                original_file,
                fixed_file_content,
                start_line=start_line,
                end_line=end_line
            )

            # Apply fix, validate, and extract diagnostics (with baseline for categorization)
            extracted_rows = self._apply_and_validate(
                original_file, project, fixed_file_content, 
                start_line, end_line, row.get("iteration_id"),
                baseline_errors=baseline_errors,  # Pass baseline for categorization
                original_problem_oid=row.get("oid")  # Link new errors to original problem
            )

            # Calculate error counts with categorization
            error_counts = self._calculate_error_metrics(extracted_rows, original_file, baseline_errors)
            print(f'[Metrics] Total: {error_counts["total"]}, Original: {error_counts["original"]}, '
                  f'New (any): {error_counts["new"]}, Truly New: {error_counts["new_to_dataset"]}, '
                  f'Introduced This Iteration: {error_counts["introduced_this_iteration"]}, File: {error_counts["in_file"]}')

            # Evaluate if error was resolved
            resolution_metrics = self._evaluate_resolution_metrics(
                row, extracted_rows, start_line, end_line, fixed_file_content
            )

            # Create and save outcome row
            outcome_row = self._create_outcome_row(
                row, original_file, resolution_metrics, error_counts
            )
            pd.DataFrame([outcome_row]).to_csv(self.outcomes_csv, mode='a', header=False, index=False)

            # Restore original file
            FixApplier.restore_original(original_file, backup_path)

