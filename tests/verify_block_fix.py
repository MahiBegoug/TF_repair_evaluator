import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from terraform_validation.extractor import _find_hcl_block

file_lines = [
    'resource "azurerm_subnet" "nodes" {',
    '  name                 = "${var.stack_name}-nodes"',
    '  resource_group_name  = azurerm_resource_group.resource_group.name',
    '  virtual_network_name = azurerm_virtual_network.virtual_network.name',
    '  address_prefix       = var.private_subnet_cidr',
    '}'
]

# Test line 5 (address_prefix) which is index 4
# Previously, it would match line 3 (resource_group_name) as a 'resource' block
result = _find_hcl_block(file_lines, 5)
print(f"Result for line 5: {result}")

if result and result['start_line'] == 1 and result['block_type'] == 'resource':
    print("SUCCESS: Found correct top-level block!")
else:
    print("FAILURE: Did not find correct block.")
