# error_matcher.py
"""
Helper service for matching errors between original and post-fix diagnostics.
Provides clean separation of concerns for error evaluation logic.

Key design principle (Issue 4 fix):
  Evaluation is row-by-row, one OID at a time. A single block can contain multiple
  errors on DIFFERENT lines with IDENTICAL (block_identifiers, summary, detail) —
  e.g. consecutive `ingress {}` or `set {}` sub-blocks. A fuzzy line-window (tolerance)
  incorrectly flags sibling errors as "unfixed". The correct strategy is:

      exact line_start  +  summary  +  block_type   (triple match)

  Only if all three match do we declare the original error is still present.
  block_type is required because `resource` and `data` blocks can share the same
  block_identifiers (user's TODO resolved here).
"""


class ErrorMatchingService:
    """
    Service for determining if errors have been resolved after applying fixes.
    Uses exact line + summary + block_type matching to handle consecutive
    identical-looking sub-blocks within the same parent block.
    """

    def __init__(self, line_tolerance=3):
        """
        Args:
            line_tolerance: Kept for _is_renamed_block_match and position-fallback
                            only. NOT used in the primary matching paths.
        """
        self.line_tolerance = line_tolerance

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def check_line_is_clean(self, original_line, original_summary, extracted_errors):
        """
        Check if the specific error at ``original_line`` is gone after the fix.

        Uses EXACT line match + summary match so that sibling errors on nearby
        lines (consecutive ingress/set blocks with the same type) are NOT
        mistakenly treated as evidence that this fix failed.

        Args:
            original_line:    Exact line_start from problems.csv for this OID.
            original_summary: The error summary string for this OID.
            extracted_errors: List of error dicts from post-fix terraform validate.

        Returns:
            bool | None: True  = line is clean (error gone)
                         False = same error still present at the same line
                         None  = original_line unknown, cannot evaluate
        """
        if original_line == -1 or original_line is None:
            return None

        try:
            original_line = int(original_line)
        except (ValueError, TypeError):
            return None

        for error in extracted_errors:
            try:
                error_line = int(error.get("line_start", -1))
            except (ValueError, TypeError):
                continue

            if error_line == -1:
                continue

            # Exact line match is required to disambiguate consecutive sub-blocks
            if error_line == original_line:
                # Also require same summary so an unrelated error on the same
                # line does not count as "unfixed"
                if error.get("summary", "").strip() == str(original_summary).strip():
                    return False  # Same error, same line → still broken

        return True   # No matching error found at the original line

    def check_specific_error_fixed(self,
                                   original_error_info,
                                   original_count,
                                   extracted_errors,
                                   fix_context):
        """
        Check if the specific error instance has been resolved.

        Matching strategy (most precise → fallback):
          1. Block-Bounded Delta Counting: compares the exact count of this error 
             in the block before and after the fix. Fix succeeds if count drops.
          2. Position-only fallback (when no block_identifiers available)

        Args:
            original_error_info: Dict with keys: summary, block_identifiers, block_type, etc.
            original_count: The number of times this exact error appeared in this block originally.
            extracted_errors: List of error dicts from post-fix validation.
            fix_context: Dict with start_line, end_line, fixed_file_content.

        Returns:
            bool: True if the specific error is gone, False if still present.
        """
        # 1. Primary Strategy: Delta Counting
        delta_result = self._check_block_delta_count(original_error_info, original_count, extracted_errors)
        if delta_result is not None:
            return delta_result

        # 2. Fallbacks (used only if block_identifiers are missing from the parsed diagnostic)
        for error in extracted_errors:
            if self._matches_by_position(error, original_error_info, fix_context):
                return False   # Positional fallback matched, error still there

        return True   # Error is gone

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _check_block_delta_count(self, original_error_info, original_count, extracted_errors):
        """
        Evaluates fix success by comparing the density of a specific error inside its block.
        Mathematically handles line shifts and identical sibling errors without relying
        on exact line tracking across iterations.
        """
        # Optional: include filename in the identity to avoid collisions where the same
        # (block_type, block_identifiers, summary) appears in multiple files within the module.
        try:
            from repair_pipeline.file_resolver import FileCoordinateResolver
            target_filename = FileCoordinateResolver.normalize_path(original_error_info.get("filename", ""))
        except Exception:
            target_filename = str(original_error_info.get("filename", "") or "").strip().replace("\\", "/")

        target_id = str(original_error_info.get("block_identifiers", "")).strip()
        target_type = str(original_error_info.get("block_type", "")).strip()
        target_summary = str(original_error_info.get("summary", "")).strip()

        # Delta counting requires valid block identifiers
        if not target_id:
            return None

        # Deduplicate identical errors emitted multiple times by terraform due to module calls.
        # Errors from the same module invocation will have the EXACT same line_start in the post-fix file,
        # whereas true architectural sibling errors will have different line_starts (even if shifted).
        unique_instances = set()
        
        for error in extracted_errors:
            # If we know the original file, require the post-fix diagnostic to be in that same file.
            if target_filename:
                try:
                    from repair_pipeline.file_resolver import FileCoordinateResolver
                    err_filename = FileCoordinateResolver.normalize_path(error.get("filename", ""))
                except Exception:
                    err_filename = str(error.get("filename", "") or "").strip().replace("\\", "/")
                if err_filename != target_filename:
                    continue

            err_id = str(error.get("block_identifiers", "")).strip()
            err_type = str(error.get("block_type", "")).strip()
            err_summary = str(error.get("summary", "")).strip()

            if err_id == target_id and err_type == target_type and err_summary == target_summary:
                line_start = error.get("line_start", -1)
                # Use (filename, line_start) so identical-looking errors in different files
                # don't collapse into one instance.
                unique_instances.add((target_filename, line_start))
                
        new_count = len(unique_instances)
        
        # Ensure mathematical safety
        try:
            safe_original_count = int(original_count)
        except (ValueError, TypeError):
            safe_original_count = 1
            
        return new_count < safe_original_count

    def _matches_by_position(self, error, original_error_info, fix_context):
        """
        Last-resort fallback: used only when the post-fix error has NO
        block_identifiers (terraform parser produced a partial diagnostic).

        Checks if the error lands inside the replaced block region and has the
        same summary. Without identifiers we cannot be more precise.

        Returns:
            bool: True if this appears to be the same error.
        """
        # Only activate this path when identifiers are missing
        current_identifiers = str(error.get("block_identifiers", "")).strip()
        if current_identifiers:
            return False

        try:
            error_line = int(error.get("line_start", -1))
            if error_line == -1:
                return False

            start_line = fix_context.get("start_line", 1)
            fixed_content = fix_context.get("fixed_file_content")
            new_line_count = len(fixed_content.splitlines()) if fixed_content else 0

            check_start = start_line
            check_end = start_line + new_line_count

            if check_start <= error_line <= check_end:
                return (error.get("summary", "").strip() ==
                        str(original_error_info.get("summary", "")).strip())
        except (ValueError, TypeError):
            pass

        return False

    def _position_matches(self, error_line, original_line, tolerance=None):
        """
        Utility: fuzzy line comparison (kept for external callers if any).
        NOT used in the primary matching paths.
        """
        if tolerance is None:
            tolerance = self.line_tolerance
        if error_line == -1 or original_line == -1:
            return False
        return abs(error_line - original_line) <= tolerance
