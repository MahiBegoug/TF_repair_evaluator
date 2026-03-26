import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from quality_metrics.block_finder import StandaloneBlockFinder

def challenge_finder():
    challenge_dir = os.path.join(project_root, "clones/challenge_project")
    os.makedirs(challenge_dir, exist_ok=True)
    
    # Challenge 1: Nested blocks (the one the user asked about)
    hcl_nested = """
resource "azurerm_virtual_network" "test" {
  name = "test"
  subnet {
    name = "sub"
    address_prefix = "10.0.1.0/24"
  }
}
"""
    f1 = os.path.join(challenge_dir, "nested.tf")
    with open(f1, "w") as f: f.write(hcl_nested)

    # Challenge 2: Malformed HCL (Missing brace)
    hcl_malformed = """
resource "azurerm_resource_group" "bad" {
  name = "bad"
  # Missing closing brace
"""
    f2 = os.path.join(challenge_dir, "malformed.tf")
    with open(f2, "w") as f: f.write(hcl_malformed)

    # Challenge 3: Top-level vs. Middle-level
    hcl_complex = """
variable "prefix" {
  default = "test"
}

locals {
  common_tags = {
    env = "prod"
  }
}
"""
    f3 = os.path.join(challenge_dir, "complex.tf")
    with open(f3, "w") as f: f.write(hcl_complex)

    print("--- CHALLENGING StandaloneBlockFinder ---")
    
    # Test 1: Nested Wrapper
    print("\nTest 1: Does it pick the WRAPPER (Parent)?")
    finder1 = StandaloneBlockFinder(f1)
    # Line 5 is inside 'subnet'
    b1 = finder1.find_block_at_line(5)
    print(f"Target: Line 5 (inside subnet)")
    print(f"Result: {b1.get('address') if b1 else 'None'}")
    if b1 and "azurerm_virtual_network" in b1.get('address', ''):
        print("PASS: Wrapper block correctly prioritized.")
    else:
        print("FAIL: Nested block returned instead of wrapper.")

    # Test 2: Malformed HCL
    print("\nTest 2: How does it handle malformed HCL (missing brace)?")
    try:
        finder2 = StandaloneBlockFinder(f2)
        b2 = finder2.find_block_at_line(2)
        print(f"Result: {b2.get('address') if b2 else 'None'}")
    except Exception as e:
        print(f"ERROR: Finder crashed on malformed HCL: {e}")

    # Test 3: Multiple top-level blocks
    print("\nTest 3: Multiple top-level blocks in one file.")
    finder3 = StandaloneBlockFinder(f3)
    b3_var = finder3.find_block_at_line(2)
    b3_loc = finder3.find_block_at_line(6)
    print(f"Line 2 (variable): {b3_var.get('address') if b3_var else 'None'}")
    print(f"Line 6 (locals):   {b3_loc.get('address') if b3_loc else 'None'}")

if __name__ == "__main__":
    challenge_finder()
