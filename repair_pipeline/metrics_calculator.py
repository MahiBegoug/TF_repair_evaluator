"""
Metrics Calculator

Handles calculation of error metrics and resolution evaluation for the repair pipeline.
"""
import os


class MetricsCalculator:
    """Calculates error metrics and evaluates resolution status."""
    
    def __init__(self, clones_root="clones", error_matcher=None, problems_dataset=None):
        """
        Initialize metrics calculator.
        
        Args:
            clones_root: Root directory for cloned repositories
            error_matcher: ErrorMatchingService instance for resolution evaluation
            problems_dataset: DataFrame with problem information (optional)
        """
        self.clones_root = clones_root
        self.error_matcher = error_matcher
        self.problems = problems_dataset
    
    def calculate_error_metrics(self, extracted_rows, original_file, baseline_errors=None):
        """
        Calculate error counts at different scopes with categorization.
        
        Args:
            extracted_rows: List of extracted error dictionaries
            original_file: Path to the original file being fixed
            baseline_errors: Set of baseline error signatures (optional)
            
        Returns:
            dict: Error counts by category
        """
        original_file_normalized = os.path.normpath(original_file)
        
        errors_in_file = sum(
            1 for er in extracted_rows 
            if os.path.normpath(os.path.join(self.clones_root, er.get("filename", "").replace("clones/", ""))) == original_file_normalized
        )
        
        # Count original vs new errors
        original_errors = sum(1 for er in extracted_rows if er.get('is_original_error', False))
        new_errors = sum(1 for er in extracted_rows if er.get('is_new_error', False))
        new_to_dataset = sum(1 for er in extracted_rows if er.get('is_new_to_dataset', False))
        introduced_this_iteration = sum(1 for er in extracted_rows if er.get('introduced_in_this_iteration', False))
        
        return {
            "total": len(extracted_rows),
            "in_file": errors_in_file,
            "in_module": len(extracted_rows),
            "original": original_errors,  # Ghost errors from before fix
            "new": new_errors,  # Errors introduced by fix (DEPRECATED - includes both new and existing)
            "new_to_dataset": new_to_dataset,  # Truly new errors never seen before
            "introduced_this_iteration": introduced_this_iteration  # Errors introduced by THIS iteration
        }
    
    def evaluate_resolution_metrics(self, row, extracted_rows, start_line, end_line, fixed_file_content):
        """
        Evaluate whether the original error was resolved.
        
        Args:
            row: Pandas Series or dict with fix data
            extracted_rows: List of extracted error dictionaries
            start_line: Start line of the fix
            end_line: End line of the fix
            fixed_file_content: Content of the fixed file
            
        Returns:
            dict: Resolution metrics (line_is_clean, specific_error_fixed)
        """
        line_is_clean = None
        specific_error_fixed = None
        
        if self.problems is not None and "oid" in row:
            target_oid = str(row["oid"])
            p_match = self.problems[self.problems["oid"].astype(str) == target_oid]

            if not p_match.empty:
                # Prepare original error information
                try:
                    original_line = int(p_match.iloc[0].get("line_start", -1))
                except (ValueError, TypeError):
                    original_line = -1
                
                original_error_info = {
                    "summary": p_match.iloc[0].get("summary", ""),
                    "block_identifiers": str(p_match.iloc[0].get("block_identifiers", "")).strip(),
                    "line_start": original_line,
                    "impacted_block_start_line": p_match.iloc[0].get("impacted_block_start_line", -1),
                    "impacted_block_end_line": p_match.iloc[0].get("impacted_block_end_line", -1)
                }
                
                fix_context = {
                    "start_line": start_line,
                    "end_line": end_line,
                    "fixed_file_content": fixed_file_content
                }
                
                # Use ErrorMatchingService for evaluation
                if self.error_matcher:
                    line_is_clean = self.error_matcher.check_line_is_clean(
                        original_line, 
                        extracted_rows
                    )
                    
                    specific_error_fixed = self.error_matcher.check_specific_error_fixed(
                        original_error_info,
                        extracted_rows,
                        fix_context
                    )
        
        return {
            "line_is_clean": line_is_clean,
            "specific_error_fixed": specific_error_fixed
        }
    
    def create_outcome_row(self, row, original_file, resolution_metrics, error_counts):
        """
        Create outcome row for CSV output with enhanced tracking.
        
        Args:
            row: Pandas Series or dict with fix data
            original_file: Path to the original file
            resolution_metrics: Dict with resolution evaluation results
            error_counts: Dict with error count metrics
            
        Returns:
            dict: Outcome row for CSV
        """
        # Convert to relative path
        try:
            relative_filename = os.path.relpath(original_file, os.getcwd())
            relative_filename = relative_filename.replace("\\", "/")
        except (ValueError, OSError):
            relative_filename = original_file
        
        return {
            "oid": row.get("oid", ""),
            "iteration_id": row.get("iteration_id", ""),
            "llm_name": row.get("llm_name", ""),
            "filename": relative_filename,
            "line_is_clean": resolution_metrics["line_is_clean"],
            "line_specific_error_fixed": resolution_metrics["specific_error_fixed"],
            "module_total_errors": error_counts["total"],
            "file_errors": error_counts["in_file"],
            "module_errors": error_counts["in_module"],
            "module_original_errors_remaining": error_counts.get("original", 0),  # Ghost errors
            "module_fix_introduced_errors": error_counts.get("introduced_this_iteration", 0)  # Errors introduced BY THIS iteration
        }
