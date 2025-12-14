# apply_fix.py
import os
import shutil


class FixApplier:
    """
    Apply LLM fixes directly into original Terraform files.
    No temporary fix files are created.
    """

    @staticmethod
    def apply_fix(original_file: str, llm_fixed_content: str) -> str:
        """
        original_file      → path to the .tf file inside clones/*
        llm_fixed_content  → RAW Terraform code suggested by the LLM

        Returns:
            backup_path (so caller can restore later)
        """

        original_file = os.path.abspath(original_file)

        print("[FIX] Original TF:", original_file)

        if not os.path.exists(original_file):
            raise FileNotFoundError(f"Original missing: {original_file}")

        # ---------- BACKUP ORIGINAL ----------
        backup_path = original_file + ".bak"
        shutil.copyfile(original_file, backup_path)

        # ---------- APPLY LLM FIX (DIRECT WRITE) ----------
        with open(original_file, "w", encoding="utf-8") as f:
            f.write(llm_fixed_content)

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
