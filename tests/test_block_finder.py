import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from quality_metrics.block_finder import StandaloneBlockFinder

def test_block_finder():
    test_file = os.path.join(project_root, "clones/test_project/main.tf")
    if not os.path.exists(test_file):
        print(f"Error: Test file {test_file} not found.")
        return

    print(f"Testing StandaloneBlockFinder with {test_file}")
    finder = StandaloneBlockFinder(test_file)

    # Line 12 is inside 'azurerm_virtual_network'
    print("\nChecking line 12 (Direct match inside azurerm_virtual_network)...")
    b1 = finder.find_block_at_line(12)
    if b1:
        print(f"Address:  {b1.get('address')}")
        print(f"Type:     {b1.get('block_type')}")
        print(f"Range:    {b1.get('start_line')} to {b1.get('end_line')}")
    else:
        print("No block found for line 12.")

    # Line 14 is inside 'subnet' block which is nested inside 'azurerm_virtual_network'
    print("\nChecking line 14 (Nested block detection)...")
    matches = []
    for b in finder.blocks:
        if b['start_line'] <= 14 <= b['end_line']:
            matches.append(b)
    
    print(f"Number of matches for line 14: {len(matches)}")
    for i, m in enumerate(matches):
        print(f"Match {i}: {m.get('address')} ({m.get('start_line')} to {m.get('end_line')})")
        
    b2 = finder.find_block_at_line(14)
    if b2:
        print(f"Smallest match: {b2.get('address')}")

if __name__ == "__main__":
    test_block_finder()
