"""
Test script for the external backup strategy.
Tests that backups are moved outside the module directory.
"""

import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.abspath('.'))

from repair_pipeline.apply_fix import FixApplier

def test_backup_strategy():
    """Test that backup is created outside the module directory."""
    
    print("=" * 60)
    print("Testing External Backup Strategy")
    print("=" * 60)
    
    # Create a test directory and file
    test_dir = os.path.join(os.getcwd(), "test_module")
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = os.path.join(test_dir, "main.tf")
    
    # Create original content
    original_content = """resource "kubernetes_namespace" "test" {
  metadata {
    name = "test"
  }
}
"""
    
    with open(test_file, "w") as f:
        f.write(original_content)
    
    print(f"\n1. Created test file: {test_file}")
    print(f"   Module directory: {test_dir}")
    
    # List files in module before fix
    print(f"\n2. Files in module BEFORE fix:")
    for f in os.listdir(test_dir):
        print(f"   - {f}")
    
    # Apply a fix
    fixed_content = """resource "kubernetes_namespace_v1" "test" {
  metadata {
    name = "test"
  }
}
"""
    
    print(f"\n3. Applying fix...")
    backup_path = FixApplier.apply_fix(test_file, fixed_content)
    
    print(f"\n4. Backup location: {backup_path}")
    print(f"   Backup in temp dir: {os.path.dirname(backup_path)}")
    print(f"   System temp dir: {tempfile.gettempdir()}")
    
    # Verify backup is NOT in module directory
    print(f"\n5. Files in module AFTER fix (backup should NOT be here):")
    module_files = os.listdir(test_dir)
    for f in module_files:
        print(f"   - {f}")
    
    # Check if backup exists in temp
    backup_exists = os.path.exists(backup_path)
    backup_in_temp = backup_path.startswith(tempfile.gettempdir())
    backup_not_in_module = os.path.dirname(backup_path) != test_dir
    
    print(f"\n6. Verification:")
    print(f"   ✓ Backup exists: {backup_exists}")
    print(f"   ✓ Backup in temp directory: {backup_in_temp}")
    print(f"   ✓ Backup NOT in module directory: {backup_not_in_module}")
    
    # Verify fixed content is in original location
    with open(test_file, "r") as f:
        current_content = f.read()
    
    has_fix = "kubernetes_namespace_v1" in current_content
    print(f"   ✓ Fixed content applied: {has_fix}")
    
    # Restore original
    print(f"\n7. Restoring original...")
    FixApplier.restore_original(test_file, backup_path)
    
    # Verify restoration
    with open(test_file, "r") as f:
        restored_content = f.read()
    
    is_restored = "kubernetes_namespace" in restored_content and "kubernetes_namespace_v1" not in restored_content
    print(f"   ✓ Original content restored: {is_restored}")
    
    # Check backup is gone
    backup_removed = not os.path.exists(backup_path)
    print(f"   ✓ Backup removed from temp: {backup_removed}")
    
    # Cleanup
    os.remove(test_file)
    os.rmdir(test_dir)
    
    # Final result
    print("\n" + "=" * 60)
    if all([backup_exists, backup_in_temp, backup_not_in_module, has_fix, is_restored, backup_removed]):
        print("✅ ALL TESTS PASSED!")
        print("✅ Backup strategy works correctly!")
        print("✅ Terraform will NOT see backup files during validation!")
    else:
        print("❌ SOME TESTS FAILED - Check output above")
    print("=" * 60)


if __name__ == "__main__":
    test_backup_strategy()
