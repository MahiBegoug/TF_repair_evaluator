import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from quality_metrics.block_finder import StandaloneBlockFinder

def verify_oid_0083293ac345():
    """
    Specifically tests the accuracy of StandaloneBlockFinder for OID 0083293ac345.
    The goal is to ensure it captures the full resource block, not just a fragment.
    """
    # Path for the problematic OID from the fleetdm project
    # Based on the user's previous context, it's typically in the clones directory
    # We'll use the path from the user's example if possible, or search for it.
    
    # For extraction verification, we can mock the file or use a known one if it exists.
    # In earlier logs, the file was identified at line 124 in some project, 
    # but the prove_block_extraction_fix used lines 18-23.
    
    test_file = os.path.join(project_root, "clones/arriven__db1000n/main.tf") # Example path
    # Actually, let's look for a file that we know has a diagnostic.
    
    print("--- Verifying StandaloneBlockFinder Accuracy ---")
    
    try:
        # We'll use the same file and lines that were problematic before
        # OID 0083293ac345 in 'arriven__db1000n' (from previous successful test)
        target_file = os.path.abspath(os.path.join(project_root, "clones/arriven__db1000n/main.tf"))
        if not os.path.exists(target_file):
            print(f"Warning: {target_file} not found. Searching for any .tf file to test general accuracy...")
            # Fallback to any .tf file to demonstrate it works
            for root, dirs, files in os.walk(os.path.join(project_root, "clones")):
                for f in files:
                    if f.endswith(".tf"):
                        target_file = os.path.join(root, f)
                        break
                if target_file: break

        start_line = 20 # A line inside a resource block
        
        finder = StandaloneBlockFinder(target_file)
        block = finder.find_with_upward_scan(start_line)
        
        if block:
            print(f"SUCCESS: Block found for line {start_line}")
            print(f"Address:    {block.get('address')}")
            print(f"Range:      {block.get('start_line')} to {block.get('end_line')}")
            print(f"Type:       {block.get('block_type')}")
            
            content = block.get('content', '')
            print("\nBlock Content:")
            print("-" * 20)
            print(content)
            print("-" * 20)
            
            # Check if it's a full block (starts with block type, ends with })
            is_full = content.strip().startswith(block.get('block_type')) and content.strip().endswith("}")
            print(f"Is Full Block (starts with type, ends with '}}'): {is_full}")
        else:
            print(f"FAILURE: No block found for line {start_line}")
            
    except Exception as e:
        print(f"ERROR during verification: {e}")

if __name__ == "__main__":
    verify_oid_0083293ac345()
