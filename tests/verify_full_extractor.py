import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from terraform_validation.extractor import DiagnosticsExtractor

def test_extraction():
    # Mocking what main.py would pass
    project_name = "SUSE__skuba"
    module_path = os.path.join(os.getcwd(), "clones/SUSE__skuba/ci/infra/azure")
    project_root = os.path.join(os.getcwd(), "clones/SUSE__skuba")
    
    # Mock diagnostic for 0083293ac345
    # address: azurerm_subnet.nodes (line 22)
    result = {
        "path": module_path,
        "diagnostics": [
            {
                "severity": "error",
                "summary": "Invalid address prefix",
                "detail": "address_prefix must be a valid CIDR",
                "range": {
                    "filename": "network.tf",
                    "start": {"line": 22, "column": 3},
                    "end": {"line": 22, "column": 20}
                }
            }
        ]
    }
    
    rows = DiagnosticsExtractor.extract_rows(project_name, result, project_root)
    
    for row in rows:
        print("-" * 40)
        print(f"OID: {row['oid']}")
        print(f"Block Type: {row['block_type']}")
        print(f"Block Identifiers: {row['block_identifiers']}")
        print(f"Lines: {row['impacted_block_start_line']} - {row['impacted_block_end_line']}")
        print("Content Excerpt:")
        print("\n".join(row['impacted_block_content'].splitlines()[:2]))
        print("-" * 40)

if __name__ == "__main__":
    test_extraction()
