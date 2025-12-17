"""
Quick test to verify error categorization columns are correctly written to CSV
"""
import os
import sys
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terraform_validation.writer import DiagnosticsWriter

# Create test data with error categorization
test_rows = [
    {
        "project_name": "test_project",
        "working_directory": ".",
        "severity": "error",
        "summary": "Missing required argument",
        "detail": "block 'test' requires 'name' attribute",
        "filename": "main.tf",
        "line_start": 10,
        "col_start": 1,
        "line_end": 15,
        "col_end": 2,
        "file_content": "resource \"test\" {}",
        "block_type": "resource",
        "block_identifiers": "aws_instance test",
        "impacted_block_start_line": 10,
        "impacted_block_end_line": 15,
        "impacted_block_content": "resource \"aws_instance\" \"test\" {}",
        "is_original_error": True,  # Ghost error
        "is_new_error": False
    },
    {
        "project_name": "test_project",
        "working_directory": ".",
        "severity": "error",
        "summary": "Invalid syntax",
        "detail": "unexpected token",
        "filename": "main.tf",
        "line_start": 20,
        "col_start": 5,
        "line_end": 20,
        "col_end": 10,
        "file_content": "resource \"test\" {}",
        "block_type": "resource",
        "block_identifiers": "aws_s3_bucket my_bucket",
        "impacted_block_start_line": 20,
        "impacted_block_end_line": 25,
        "impacted_block_content": "resource \"aws_s3_bucket\" \"my_bucket\" {}",
        "is_original_error": False,
        "is_new_error": True  # Fix-introduced error
    }
]

# Write to test CSV
test_csv = "test_categorization_output.csv"
if os.path.exists(test_csv):
    os.remove(test_csv)

DiagnosticsWriter.write_rows(test_rows, test_csv, iteration_id="test_iter_1")

# Read back and verify
df = pd.read_csv(test_csv)

print("✓ CSV created successfully")
print(f"✓ Total rows: {len(df)}")
print(f"✓ Columns: {list(df.columns)}")

# Verify new columns exist
assert "is_original_error" in df.columns, "Missing is_original_error column"
assert "is_new_error" in df.columns, "Missing is_new_error column"
print("✓ Error categorization columns present")

# Verify data integrity
assert df.iloc[0]["is_original_error"] == True, "First row should be ghost error"
assert df.iloc[0]["is_new_error"] == False, "First row should not be new error"
assert df.iloc[1]["is_original_error"] == False, "Second row should not be ghost error"
assert df.iloc[1]["is_new_error"] == True, "Second row should be new error"
print("✓ Error categorization values correct")

# Test filtering (as user wanted)
ghosts = df[df['is_original_error'] == True]
new_errors = df[df['is_new_error'] == True]

print(f"✓ Ghost errors: {len(ghosts)}")
print(f"✓ New errors: {len(new_errors)}")

# Cleanup
os.remove(test_csv)
print("\n✅ All tests passed! Error categorization is working correctly.")
