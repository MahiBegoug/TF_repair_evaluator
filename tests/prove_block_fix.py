import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from terraform_validation.extractor import _find_hcl_block

# The exact problematic content from SUSE__skuba/ci/infra/azure/network.tf
file_lines = [
    'resource "azurerm_subnet" "nodes" {',     # line 1
    '  name                 = "${var.stack_name}-nodes"', # line 2
    '  resource_group_name  = azurerm_resource_group.resource_group.name', # line 3
    '  virtual_network_name = azurerm_virtual_network.virtual_network.name', # line 4
    '  address_prefix       = var.private_subnet_cidr', # line 5
    '}' # line 6
]

# Error is on line 5 (address_prefix)
# Previously, walking up from line 5 would match line 3 (resource_group_name) as a 'resource' block
result = _find_hcl_block(file_lines, 5)

print("-" * 40)
print(f"Extraction result for line 5:")
print(f"Block Type: {result.get('block_type')}")
print(f"Start Line: {result.get('start_line')}")
print(f"End Line:   {result.get('end_line')}")
print("-" * 40)
print("Impacted Block Content:")
print("\n".join(file_lines[result['start_line']-1 : result['end_line']]))
print("-" * 40)
