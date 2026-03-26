# Manual verification of the max() logic for StandaloneBlockFinder
matches = [
    {'address': 'resource.azurerm_virtual_network.example', 'start_line': 6, 'end_line': 16},
    {'address': 'subnet', 'start_line': 12, 'end_line': 15}
]

# Pick the one with the largest range (the wrapper)
wrapper = max(matches, key=lambda x: x['end_line'] - x['start_line'])
print(f"Wrapper identified: {wrapper['address']} ({wrapper['start_line']} to {wrapper['end_line']})")

expected = 'resource.azurerm_virtual_network.example'
if wrapper['address'] == expected:
    print("SUCCESS: max() logic correctly identifies the parent/wrapper block.")
else:
    print(f"FAILURE: Expected {expected}, got {wrapper['address']}")
