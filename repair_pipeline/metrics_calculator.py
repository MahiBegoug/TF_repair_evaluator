"""
Metrics Calculator

Handles calculation of error metrics and resolution evaluation for the repair pipeline.
"""
import os
from repair_pipeline.file_resolver import FileCoordinateResolver
from repair_pipeline.debug import dprint, is_debug_matching_enabled


class MetricsCalculator:
    """Calculates error metrics and evaluates resolution status."""
    
    def __init__(self, clones_root="clones", error_matcher=None, problems_dataset=None, debug_matching: bool | None = None):
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
        self.debug_matching = is_debug_matching_enabled(debug_matching)
        # Build lookup indices for both OID types
        self._problems_by_oid = {}          # Legacy location-based grouping
        self._problems_by_specific_oid = {} # High-fidelity matching key
        self._original_error_counts = {}
        
        # Track physical locations to deduplicate module-call echoes
        seen_physical_locations = {}
        
        if problems_dataset is not None and not problems_dataset.empty:
            for _, row in problems_dataset.iterrows():
                oid_key = str(row.get("oid", "")).strip()
                spec_oid_key = str(row.get("specific_oid", "")).strip()
                
                # Index by both OIDs for maximum flexibility
                if oid_key and oid_key not in self._problems_by_oid:
                    self._problems_by_oid[oid_key] = row
                if spec_oid_key and spec_oid_key not in self._problems_by_specific_oid:
                    self._problems_by_specific_oid[spec_oid_key] = row
                
                # Build block-scoped error count index with robust normalization
                count_key = (
                    FileCoordinateResolver.normalize_path(row.get("filename", "")),
                    str(row.get("block_type", "")).strip(),
                    str(row.get("block_identifiers", "")).strip(),
                    str(row.get("summary", "")).strip().lower()
                )
                
                line_start = row.get("line_start", -1)
                
                if count_key not in seen_physical_locations:
                    seen_physical_locations[count_key] = set()
                    
                # Only count the error if it's on a new physical line in the original file
                if line_start not in seen_physical_locations[count_key]:
                    seen_physical_locations[count_key].add(line_start)
                    self._original_error_counts[count_key] = self._original_error_counts.get(count_key, 0) + 1

            dprint(
                self.debug_matching,
                f"[DEBUG_MATCH] Baseline indices built: "
                f"by_specific_oid={len(self._problems_by_specific_oid)}, by_oid={len(self._problems_by_oid)}"
            )

    
    def calculate_error_metrics(self, extracted_rows, original_file, baseline_errors=None, target_oid=None):
        """
        Calculate error counts at different scopes with categorization.
        
        Args:
            extracted_rows: List of extracted error dictionaries
            original_file: Path to the original file being fixed
            baseline_errors: Set of baseline error signatures (optional)
            target_oid: OID of the specific problem we are fixing (optional, for block metrics)
            
        Returns:
            dict: Error counts by category
        """
        original_file_normalized = os.path.normpath(original_file)
        
        # 1. Module and File level counts
        errors_in_file = sum(
            1 for er in extracted_rows 
            if os.path.normpath(os.path.join(self.clones_root, er.get("filename", "").replace("clones/", ""))) == original_file_normalized
        )
        
        original_errors = sum(1 for er in extracted_rows if er.get('is_original_error', False))
        new_to_dataset = sum(1 for er in extracted_rows if er.get('is_new_to_dataset', False))
        introduced_this_iteration = sum(1 for er in extracted_rows if er.get('introduced_in_this_iteration', False))

        # 2. Block-level metrics: identify the scope of interest
        block_total = 0
        block_original = 0
        block_introduced = 0
        
        block_scope = None
        if target_oid:
            # First, check the baseline to see what block this OID originally belonged to
            p_row = self._problems_by_oid.get(str(target_oid))
            if p_row is not None:
                block_scope = {
                    "filename": FileCoordinateResolver.normalize_path(p_row.get("filename", "")),
                    "type": str(p_row.get("block_type", "")).strip(),
                    "idents": str(p_row.get("block_identifiers", "")).strip()
                }
        
        if block_scope and block_scope["type"]:
            for er in extracted_rows:
                # Check if this remaining/new error matches the target block's identity
                er_filename = FileCoordinateResolver.normalize_path(er.get("filename", ""))
                er_type = str(er.get("block_type", "")).strip()
                er_idents = str(er.get("block_identifiers", "")).strip()
                
                if (
                    er_filename == block_scope["filename"]
                    and er_type == block_scope["type"]
                    and er_idents == block_scope["idents"]
                ):
                    block_total += 1
                    if er.get('is_original_error', False):
                        block_original += 1
                    if er.get('introduced_in_this_iteration', False):
                        block_introduced += 1

        return {
            "total": len(extracted_rows),
            "in_file": errors_in_file,
            "in_module": len(extracted_rows),
            "original": original_errors,
            "new_to_dataset": new_to_dataset,
            "introduced_this_iteration": introduced_this_iteration,
            "block_total": block_total,
            "block_original": block_original,
            "block_introduced": block_introduced
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
        p_row = None
        
        if self.problems is not None and not self.problems.empty:
            # 1. Primary Lookup (Specific OID)
            # Re-calculate specific_oid for the LLM response row to ensure parity
            from terraform_validation.extractor import DiagnosticsExtractor
            target_spec_oid = DiagnosticsExtractor.compute_specific_oid(row)
            dprint(
                self.debug_matching,
                f"[DEBUG_MATCH] resolution lookup start oid={row.get('oid')} computed_specific_oid={target_spec_oid} "
                f"project={row.get('project_name')} filename={FileCoordinateResolver.normalize_path(row.get('filename', ''))} "
                f"lines={row.get('line_start')}-{row.get('line_end')}"
            )
            
            p_row = self._problems_by_specific_oid.get(target_spec_oid)
            dprint(
                self.debug_matching,
                f"[DEBUG_MATCH] resolution lookup hit=specific_oid {bool(p_row is not None)} "
                f"computed_specific_oid={target_spec_oid}"
            )
            
            # 2. Fallback Lookup (Legacy OID)
            if p_row is None and "oid" in row:
                target_oid = str(row["oid"]).strip()
                p_row = self._problems_by_oid.get(target_oid)
                dprint(
                    self.debug_matching,
                    f"[DEBUG_MATCH] resolution lookup hit=oid {bool(p_row is not None)} oid={target_oid}"
                )

            if p_row is not None:
                # Prepare original error information
                try:
                    original_line = int(p_row.get("line_start", -1))
                except (ValueError, TypeError):
                    original_line = -1
                
                original_error_info = {
                    # Used for safe block-bounded matching when identical identifiers exist in multiple files.
                    "filename": FileCoordinateResolver.normalize_path(p_row.get("filename", "")),
                    "summary": p_row.get("summary", ""),
                    "block_identifiers": str(p_row.get("block_identifiers", "")).strip(),
                    # block_type distinguishes resource vs data blocks with same identifiers
                    "block_type": str(p_row.get("block_type", "")).strip(),
                    "line_start": original_line,
                    "impacted_block_start_line": p_row.get("impacted_block_start_line", -1),
                    "impacted_block_end_line": p_row.get("impacted_block_end_line", -1)
                }

                fix_context = {
                    "start_line": start_line,
                    "end_line": end_line,
                    "fixed_file_content": fixed_file_content
                }

                # Use ErrorMatchingService for evaluation
                if self.error_matcher:
                    # Pass original_summary so check_line_is_clean can do
                    # exact line + summary match (avoids false unfixed on sibling errors)
                    original_summary = p_row.get("summary", "")
                    line_is_clean = self.error_matcher.check_line_is_clean(
                        original_line,
                        original_summary,
                        extracted_rows
                    )
                    
                    # Get the original density of this error in the block
                    count_key = (
                        FileCoordinateResolver.normalize_path(p_row.get("filename", "")),
                        str(p_row.get("block_type", "")).strip(),
                        str(p_row.get("block_identifiers", "")).strip(),
                        original_summary.strip().lower()
                    )
                    original_count = self._original_error_counts.get(count_key, 1)

                    specific_error_fixed = self.error_matcher.check_specific_error_fixed(
                        original_error_info,
                        original_count,
                        extracted_rows,
                        fix_context
                    )
            else:
                dprint(
                    self.debug_matching,
                    f"[DEBUG_MATCH] resolution lookup miss=all oid={row.get('oid')} computed_specific_oid={target_spec_oid}"
                )
        
        return {
            "line_is_clean": line_is_clean,
            "specific_error_fixed": specific_error_fixed,
            "matched_oid": p_row.get("oid") if p_row is not None else None,
            "matched_specific_oid": p_row.get("specific_oid") if p_row is not None else None
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
        # Use robust, systematic normalization instead of relative disk paths
        relative_filename = FileCoordinateResolver.normalize_path(original_file)
        
        # Prioritize OIDs from the baseline problem dataset for consistent tracking
        final_oid = resolution_metrics.get("matched_oid") or row.get("oid", "")
        # Always emit a specific_oid when possible. Some LLM response CSVs don't include
        # `specific_oid`, and some OIDs may be missing from the baseline problems dataset.
        # In those cases we fall back to computing it from the row itself so downstream
        # analysis doesn't end up with NaN/empty specific_oid values.
        computed_spec_oid = ""
        try:
            from terraform_validation.extractor import DiagnosticsExtractor
            computed_spec_oid = DiagnosticsExtractor.compute_specific_oid(row)
        except Exception:
            computed_spec_oid = ""

        final_spec_oid = (
            resolution_metrics.get("matched_specific_oid")
            or row.get("specific_oid", "")
            or computed_spec_oid
        )
        
        return {
            "oid": final_oid,
            "specific_oid": final_spec_oid,
            "iteration_id": row.get("iteration_id", ""),
            "llm_name": row.get("llm_name", ""),
            "filename": relative_filename,
            "is_fixed": resolution_metrics["specific_error_fixed"],
            "line_is_clean": resolution_metrics["line_is_clean"],
            "line_specific_error_fixed": resolution_metrics["specific_error_fixed"],
            "module_total_errors": error_counts["total"],
            "file_errors": error_counts["in_file"],
            "module_errors": error_counts["in_module"],
            "module_original_errors_remaining": error_counts.get("original", 0),
            "module_fix_introduced_errors": error_counts.get("introduced_this_iteration", 0),
            "block_total_errors": error_counts.get("block_total", 0),
            "block_original_errors_remaining": error_counts.get("block_original", 0),
            "block_fix_introduced_errors": error_counts.get("block_introduced", 0)
        }
