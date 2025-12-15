# error_matcher.py
"""
Helper service for matching errors between original and post-fix diagnostics.
Provides clean separation of concerns for error evaluation logic.
"""


class ErrorMatchingService:
    """
    Service for determining if errors have been resolved after applying fixes.
    Supports both line-based and error-type-based matching strategies.
    """
    
    def __init__(self, line_tolerance=3):
        """
        Args:
            line_tolerance: Number of lines +/- to consider as "same location"
        """
        self.line_tolerance = line_tolerance
    
    def check_line_is_clean(self, original_line, extracted_errors):
        """
        Check if the original error line is error-free after the fix.
        
        Args:
            original_line: Line number of the original error
            extracted_errors: List of error dictionaries from post-fix validation
            
        Returns:
            bool: True if no errors found at the original line location
        """
        if original_line == -1:
            return None
        
        for error in extracted_errors:
            try:
                error_line = int(error.get("line_start", -1))
                if error_line != -1:
                    if abs(error_line - original_line) <= self.line_tolerance:
                        return False  # Found error at this line
            except (ValueError, TypeError):
                continue
        
        return True  # No errors found at original line
    
    def check_specific_error_fixed(self, 
                                    original_error_info,
                                    extracted_errors,
                                    fix_context):
        """
        Check if the specific error type has been resolved.
        
        Args:
            original_error_info: Dict with keys:
                - summary: Error summary string
                - block_identifiers: Block identifier string
                - line_start: Original line number
                - impacted_block_start_line: Start of impacted block
                - impacted_block_end_line: End of impacted block
            extracted_errors: List of error dicts from post-fix validation
            fix_context: Dict with keys:
                - start_line: Start line of the fix
                - end_line: End line of the fix
                - fixed_file_content: The fixed content (for line counting)
                
        Returns:
            bool: True if the specific error type no longer appears
        """
        original_summary = original_error_info.get("summary", "")
        original_identifiers = str(original_error_info.get("block_identifiers", "")).strip()
        original_line = original_error_info.get("line_start", -1)
        
        for error in extracted_errors:
            # Try identifier-based matching first (strongest signal)
            if self._matches_by_identifier(error, original_error_info):
                return False  # Specific error still exists
            
            # Fallback to position-based matching
            if self._matches_by_position(error, original_error_info, fix_context):
                return False  # Specific error still exists
        
        return True  # Specific error type is gone
    
    def _matches_by_identifier(self, error, original_error_info):
        """
        Check if error matches original by block identifier and summary.
        
        Returns:
            bool: True if this is the same error
        """
        current_identifiers = str(error.get("block_identifiers", "")).strip()
        original_identifiers = str(original_error_info.get("block_identifiers", "")).strip()
        
        # Both must have identifiers for this check to be valid
        if not (original_identifiers and current_identifiers):
            return False
        
        # Different blocks = not a match
        if original_identifiers != current_identifiers:
            # Check if it's a renamed block with same position
            return self._is_renamed_block_match(error, original_error_info)
        
        # Same block - check if same error type
        if error.get("summary") != original_error_info.get("summary"):
            return False
        
        # Same block, same error type - verify position
        return self._position_matches(
            error.get("line_start", -1),
            original_error_info.get("line_start", -1)
        )
    
    def _is_renamed_block_match(self, error, original_error_info):
        """
        Check if error is on a renamed block at the same position.
        Example: kubernetes_namespace renamed to kubernetes_namespace_v1
        
        Returns:
            bool: True if same error on renamed block
        """
        current_identifiers = str(error.get("block_identifiers", "")).strip()
        original_identifiers = str(original_error_info.get("block_identifiers", "")).strip()
        
        # Both must exist but be different
        if not (current_identifiers and original_identifiers):
            return False
        if current_identifiers == original_identifiers:
            return False
        
        # Check if error is in same position as original block
        try:
            error_line = int(error.get("line_start", -1))
            original_block_start = int(original_error_info.get("impacted_block_start_line", -1))
            original_block_end = int(original_error_info.get("impacted_block_end_line", -1))
            
            if error_line == -1 or original_block_start == -1:
                return False
            
            # Check if error is within original block range (with buffer)
            if original_block_start - self.line_tolerance <= error_line <= original_block_end + self.line_tolerance:
                # Same position, check if same error type
                return error.get("summary") == original_error_info.get("summary")
        except (ValueError, TypeError, KeyError):
            pass
        
        return False
    
    def _matches_by_position(self, error, original_error_info, fix_context):
        """
        Fallback: Check if error matches by position when identifiers unavailable.
        Only used when current error has no identifier (parser failure).
        
        Returns:
            bool: True if this appears to be the same error
        """
        current_identifiers = str(error.get("block_identifiers", "")).strip()
        
        # Only use position fallback if current error has no identifier
        if current_identifiers:
            return False
        
        # Check if error is in the vicinity of the fix
        try:
            error_line = int(error.get("line_start", -1))
            if error_line == -1:
                return False
            
            # Calculate the area affected by the fix
            fixed_content = fix_context.get("fixed_file_content")
            start_line = fix_context.get("start_line", 1)
            
            if fixed_content:
                new_lines_count = len(fixed_content.splitlines())
            else:
                new_lines_count = 0
            
            buffer = 2
            check_start = start_line - buffer
            check_end = start_line + new_lines_count + buffer
            
            # Error in the affected area?
            if check_start <= error_line <= check_end:
                # Same error type?
                return error.get("summary") == original_error_info.get("summary")
        except (ValueError, TypeError):
            pass
        
        return False
    
    def _position_matches(self, error_line, original_line, tolerance=None):
        """
        Check if two line numbers are close enough to be considered the same position.
        
        Returns:
            bool: True if positions match within tolerance
        """
        if tolerance is None:
            tolerance = self.line_tolerance
        
        if error_line == -1 or original_line == -1:
            return False
        
        return abs(error_line - original_line) <= tolerance
