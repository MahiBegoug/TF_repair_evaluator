# apply_fix.py
import os
import shutil


class FixApplier:
    """
    Apply LLM fixes directly into original Terraform files.
    No temporary fix files are created.
    """

    @staticmethod
    def apply_fix(original_file: str, llm_fixed_content: str, start_line: int = None, end_line: int = None) -> str:
        """
        original_file → path to the .tf file inside clones/*
        llm_fixed_content → RAW Terraform code suggested by the LLM
        start_line → (Optional) Start line (1-based)
        end_line           → (Optional) End line (1-based)

        Returns:
            backup_path (so caller can restore later)
        """

        original_file = os.path.abspath(original_file)

        print(f"[FIX] Original TF: {original_file} (Lines: {start_line}-{end_line})")

        if not os.path.exists(original_file):
            raise FileNotFoundError(f"Original missing: {original_file}")

        # ---------- BACKUP ORIGINAL (MOVED OUTSIDE MODULE)----------
        # Move original file to temp directory OUTSIDE the module
        # This guarantees Terraform CANNOT see it during validation
        
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        # Create unique backup filename to avoid collisions
        safe_name = original_file.replace(os.sep, '_').replace(':', '_').replace('.', '_')
        backup_path = os.path.join(temp_dir, f"tfrepair_backup_{safe_name}.tf")
        
        print(f"[BACKUP] Moving original OUTSIDE module to: {backup_path}")
        shutil.move(original_file, backup_path)

        # ---------- READ BACKUP CONTENT ----------
        with open(backup_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # ---------- APPLY FIX ----------
        if start_line is not None and end_line is not None:
            # Block replacement
            # Convert 1-based lines to 0-based indices
            idx_start = start_line - 1
            idx_end = end_line 

            # Ensure we don't go out of bounds (basic check)
            if idx_start < 0: idx_start = 0
            if idx_end > len(lines): idx_end = len(lines)

            # Ensure llm_fixed_content ends with newline
            if not llm_fixed_content.endswith('\n'):
                llm_fixed_content += '\n'

            new_content = "".join(lines[:idx_start]) + llm_fixed_content + "".join(lines[idx_end:])
        else:
            # Full file replacement
            new_content = llm_fixed_content

        # ---------- WRITE FIXED CONTENT TO ORIGINAL LOCATION ----------
        with open(original_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"[FIX] Wrote LLM fix to → {original_file}")
        print(f"[SAFEGUARD] ✓ Backup is OUTSIDE module - Terraform CANNOT see it!")

        return backup_path

    @staticmethod
    def restore_original(original_file: str, backup_path: str):
        """
        Restore original Terraform file after testing.
        Moves backup from temp location back to original location.
        """

        original_file = os.path.abspath(original_file)
        backup_path = os.path.abspath(backup_path)

        if os.path.exists(backup_path):
            # Remove the fixed file first
            if os.path.exists(original_file):
                os.remove(original_file)
            
            # Move backup from temp location back to original
            shutil.move(backup_path, original_file)
            print(f"[RESTORE] Restored original from temp backup → {original_file}")
        else:
            print(f"[WARNING] Backup not found: {backup_path}")

