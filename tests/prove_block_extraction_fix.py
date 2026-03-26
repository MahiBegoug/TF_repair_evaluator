import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from terraform_validation.extractor import DiagnosticsExtractor

def test_proven_fix():
    print("Testing block extraction fix for OID 0083293ac345...")
    
    # Path to the actual network.tf from TFReproducer clones
    # (Adjusted to use absolute path found earlier)
    abs_tf_path = r"C:\Users\Admin\PycharmProjects\TFReproducer\clones\SUSE__skuba\ci\infra\azure\network.tf"
    
    if not os.path.exists(abs_tf_path):
        print(f"ERROR: Sample file not found at {abs_tf_path}")
        return

    # Mocking the diagnostic for 0083293ac345
    # project: SUSE__skuba, file: network.tf, line: 22
    result = {
        "path": os.path.dirname(abs_tf_path),
        "diagnostics": [
            {
                "severity": "error",
                "summary": "Invalid address_prefix",
                "detail": "testing address_prefix logic",
                "range": {
                    "filename": "network.tf",
                    "start": {"line": 22, "column": 3},
                    "end": {"line": 22, "column": 20}
                }
            }
        ]
    }
    
    project_name = "SUSE__skuba"
    project_root = r"C:\Users\Admin\PycharmProjects\TFReproducer\clones\SUSE__skuba"
    
    # Run the extractor
    rows = DiagnosticsExtractor.extract_rows(project_name, result, project_root)
    
    if not rows:
        print("FAIL: No rows extracted.")
        return
        
    row = rows[0]
    print(f"OID: {row['oid']}")
    print(f"Impacted Block Type: {row['impacted_block_type']}")
    print(f"Block Identifiers: {row['block_identifiers']}")
    print(f"Start Line: {row['impacted_block_start_line']}")
    print(f"End Line: {row['impacted_block_end_line']}")
    print("\nImpacted Block Content:")
    print("-" * 20)
    print(row['impacted_block_content'])
    print("-" * 20)
    
    # Validation logic
    # block_type_full for a resource with two labels (type, name) typically becomes "resource type"
    is_correct_type = row['impacted_block_type'] == "resource"
    is_correct_block = "azurerm_subnet" in row['block_type_full'] and "nodes" in row['block_identifiers']
    
    if is_correct_type and is_correct_block:
        print("\nSUCCESS: Correct full block identified!")
        print(f"Verified OID {row['oid']} now captures the complete resource from lines {row['impacted_block_start_line']} to {row['impacted_block_end_line']}.")
    else:
        print("\nFAIL: Block identification still incorrect.")
        print(f"Actual block_type_full: '{row['block_type_full']}'")
        print(f"Actual block_identifiers: '{row['block_identifiers']}'")

if __name__ == "__main__":
    test_proven_fix()
