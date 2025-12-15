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

        # ---------- BACKUP ORIGINAL ----------
        backup_path = original_file + ".bak"
        if not os.path.exists(backup_path):
             shutil.copyfile(original_file, backup_path)

        # ---------- READ ORIGINAL CONTENT ----------
        with open(original_file, "r", encoding="utf-8") as f:
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

            # We insert the new content. 
            # Note: llm_fixed_content is a string, possibly multi-line.
            # We treat it as a single block to insert/replace.
            
            # Ensure llm_fixed_content ends with newline if the block being replaced did?
            # Or just blindly insert. Terraform files usually end in newline.
            # Let's ensure the inserted content has a newline if it's not empty/just replacing in-place without one.
            if not llm_fixed_content.endswith('\n'):
                llm_fixed_content += '\n'

            new_content = "".join(lines[:idx_start]) + llm_fixed_content + "".join(lines[idx_end:])
        else:
            # Full file replacement
            new_content = llm_fixed_content

        # ---------- WRITE UTILITY ----------
        with open(original_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"[FIX] Wrote LLM repair directly into → {original_file}")

        return backup_path

    @staticmethod
    def restore_original(original_file: str, backup_path: str):
        """
        Restore original Terraform file after testing.
        """

        original_file = os.path.abspath(original_file)
        backup_path = os.path.abspath(backup_path)

        if os.path.exists(backup_path):
            shutil.move(backup_path, original_file)
            print(f"[RESTORE] Restored original → {original_file}")
