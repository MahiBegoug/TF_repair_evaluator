"""
Quick validation test for the refactored ErrorMatchingService.
Tests the key scenarios to ensure refactoring didn't break functionality.
"""
from repair_pipeline.error_matcher import ErrorMatchingService


def test_line_is_clean():
    """Test line-based checking"""
    matcher = ErrorMatchingService(line_tolerance=3)
    
    # Test Case 1: No errors at original line = clean
    original_line = 10
    errors = [
        {"line_start": 20},  # Far away
        {"line_start": 25}   # Far away
    ]
    assert matcher.check_line_is_clean(original_line, errors) == True
    print("✓ Test 1 passed: Line is clean when no errors nearby")
    
    # Test Case 2: Error within tolerance = not clean
    errors = [
        {"line_start": 11},  # Within 3 lines
    ]
    assert matcher.check_line_is_clean(original_line, errors) == False
    print("✓ Test 2 passed: Line is not clean when error within tolerance")
    
    # Test Case 3: Error exactly at tolerance boundary = not clean
    errors = [
        {"line_start": 13},  # Exactly 3 lines away
    ]
    assert matcher.check_line_is_clean(original_line, errors) == False
    print("✓ Test 3 passed: Line is not clean at tolerance boundary")
    
    # Test Case 4: Invalid line number
    original_line = -1
    errors = [{"line_start": 10}]
    assert matcher.check_line_is_clean(original_line, errors) == None
    print("✓ Test 4 passed: Returns None for invalid line")


def test_specific_error_fixed():
    """Test error-type-based checking"""
    matcher = ErrorMatchingService(line_tolerance=3)
    
    # Test Case 1: Same error persists (same identifier, same summary)
    original_error = {
        "summary": "Unsupported block type",
        "block_identifiers": "resource aws_instance example",
        "line_start": 10,
        "impacted_block_start_line": 10,
        "impacted_block_end_line": 15
    }
    
    new_errors = [
        {
            "summary": "Unsupported block type",
            "block_identifiers": "resource aws_instance example",
            "line_start": 10
        }
    ]
    
    fix_context = {"start_line": 10, "end_line": 15, "fixed_file_content": "test"}
    
    result = matcher.check_specific_error_fixed(original_error, new_errors, fix_context)
    assert result == False
    print("✓ Test 5 passed: Same error detected as not fixed")
    
    # Test Case 2: Different error type on same block (error transformation)
    new_errors = [
        {
            "summary": "Unsupported argument",  # Different!
            "block_identifiers": "resource aws_instance example",
            "line_start": 10
        }
    ]
    
    result = matcher.check_specific_error_fixed(original_error, new_errors, fix_context)
    assert result == True
    print("✓ Test 6 passed: Different error type detected as fixed")
    
    # Test Case 3: No errors = fixed
    new_errors = []
    result = matcher.check_specific_error_fixed(original_error, new_errors, fix_context)
    assert result == True
    print("✓ Test 7 passed: No errors means original is fixed")


if __name__ == "__main__":
    print("Running ErrorMatchingService validation tests...\n")
    
    test_line_is_clean()
    print()
    test_specific_error_fixed()
    
    print("\n✅ All tests passed! Refactoring is working correctly.")
