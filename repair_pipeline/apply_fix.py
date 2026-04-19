# apply_fix.py
import atexit
import os
import shutil
import signal
import tempfile
import threading


_ACTIVE_BACKUPS: dict[str, str] = {}
_ACTIVE_BACKUPS_LOCK = threading.Lock()
_SIGNAL_HANDLERS_INSTALLED = False


def _register_active_backup(original_file: str, backup_path: str):
    with _ACTIVE_BACKUPS_LOCK:
        _ACTIVE_BACKUPS[original_file] = backup_path


def _unregister_active_backup(original_file: str):
    with _ACTIVE_BACKUPS_LOCK:
        _ACTIVE_BACKUPS.pop(original_file, None)


def _snapshot_active_backups() -> list[tuple[str, str]]:
    with _ACTIVE_BACKUPS_LOCK:
        return list(_ACTIVE_BACKUPS.items())


def _restore_backup_pair(original_file: str, backup_path: str, *, reason: str) -> bool:
    original_file = os.path.abspath(original_file)
    backup_path = os.path.abspath(backup_path)

    if not os.path.exists(backup_path):
        return False

    try:
        if os.path.exists(original_file):
            os.remove(original_file)
        shutil.move(backup_path, original_file)
        print(f"[RESTORE] Restored original from temp backup ({reason}) -> {original_file}")
        return True
    except Exception as exc:
        print(f"[WARNING] Failed to restore backup for {original_file}: {exc}")
        return False
    finally:
        _unregister_active_backup(original_file)


def _restore_all_active_backups(*, reason: str) -> int:
    restored = 0
    for original_file, backup_path in _snapshot_active_backups():
        if _restore_backup_pair(original_file, backup_path, reason=reason):
            restored += 1
    return restored


def _make_signal_handler(signum: int):
    def _handler(_received_signum, _frame):
        restored = _restore_all_active_backups(reason=f"signal {signum}")
        if restored:
            print(f"[CLEANUP] Restored {restored} active backup(s) before exit.")
        raise SystemExit(128 + signum)

    return _handler


def _install_signal_handlers():
    global _SIGNAL_HANDLERS_INSTALLED
    if _SIGNAL_HANDLERS_INSTALLED:
        return

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        signal.signal(sig, _make_signal_handler(sig))

    atexit.register(_restore_all_active_backups, reason="process exit")
    _SIGNAL_HANDLERS_INSTALLED = True


_install_signal_handlers()


class FixApplier:
    """
    Apply LLM fixes directly into original Terraform files.
    No temporary fix files are created.
    """

    @staticmethod
    def apply_fix(original_file: str, llm_fixed_content: str, start_line: int = None, end_line: int = None) -> str:
        """
        original_file -> path to the .tf file inside clones/*
        llm_fixed_content -> raw Terraform code suggested by the LLM
        start_line -> optional start line (1-based)
        end_line -> optional end line (1-based)

        Returns:
            backup_path (so caller can restore later)
        """

        original_file = os.path.abspath(original_file)

        print(f"[FIX] Original TF: {original_file} (Lines: {start_line}-{end_line})")

        if not os.path.exists(original_file):
            raise FileNotFoundError(f"Original missing: {original_file}")

        # Move the original file outside the module so Terraform cannot see the backup.
        temp_dir = tempfile.gettempdir()

        # Create a unique backup filename to avoid collisions.
        safe_name = original_file.replace(os.sep, "_").replace(":", "_").replace(".", "_")
        backup_path = os.path.join(temp_dir, f"tfrepair_backup_{safe_name}.tf")

        print(f"[BACKUP] Moving original OUTSIDE module to: {backup_path}")
        shutil.move(original_file, backup_path)
        _register_active_backup(original_file, backup_path)

        with open(backup_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # LLM output may contain wrapper tags or fenced code blocks.
        import re

        cleaned_content = llm_fixed_content

        cdata_match = re.search(r"<!\[CDATA\[(.*?)\]\]>", cleaned_content, re.DOTALL)
        if cdata_match:
            cleaned_content = cdata_match.group(1)
        else:
            tags_to_strip = [
                r"<fixed_block_content.*?>",
                r"</fixed_block_content>",
                r"<analysis.*?>",
                r"</analysis>",
                r"```hcl",
                r"```",
            ]
            for tag in tags_to_strip:
                cleaned_content = re.sub(tag, "", cleaned_content, flags=re.IGNORECASE | re.DOTALL)

        cleaned_content = cleaned_content.strip()

        if cleaned_content and not cleaned_content.endswith("\n"):
            cleaned_content += "\n"

        if start_line is not None and end_line is not None:
            idx_start = start_line - 1
            idx_end = end_line

            if idx_start < 0:
                idx_start = 0
            if idx_end > len(lines):
                idx_end = len(lines)

            new_content = "".join(lines[:idx_start]) + cleaned_content + "".join(lines[idx_end:])
        else:
            new_content = cleaned_content

        with open(original_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"[FIX] Wrote LLM fix to -> {original_file}")
        print("[SAFEGUARD] Backup is outside the module; Terraform cannot see it.")

        return backup_path

    @staticmethod
    def restore_original(original_file: str, backup_path: str):
        """
        Restore original Terraform file after testing.
        Moves backup from temp location back to original location.
        """

        original_file = os.path.abspath(original_file)
        backup_path = os.path.abspath(backup_path)

        if not _restore_backup_pair(original_file, backup_path, reason="normal completion"):
            print(f"[WARNING] Backup not found: {backup_path}")

    @staticmethod
    def restore_pending_backups(reason: str = "manual cleanup") -> int:
        """
        Restore any backups still registered in the current process.
        Useful after interrupted runs or in tests.
        """

        return _restore_all_active_backups(reason=reason)
