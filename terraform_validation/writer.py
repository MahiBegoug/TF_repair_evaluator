import os
import pandas as pd
import hashlib

class DiagnosticsWriter:

    COLUMNS = [
        "project_name",
        "working_directory",
        "oid",  # NEW COLUMN (HASH)
        "original_problem_oid",  # OID of the original problem being fixed
        "iteration_id",  # Repair iteration identifier
        "severity",
        "summary",
        "detail",
        "filename",
        "line_start",
        "col_start",
        "line_end",
        "col_end",
        "file_content",
        "block_type",
        "block_identifiers",
        "impacted_block_start_line",
        "impacted_block_end_line",
        "impacted_block_content",
        "is_original_error",  # Boolean: True if error existed in baseline before any fixes
        "is_new_error",  # Boolean: True if error was introduced by a fix (DEPRECATED - use is_new_to_dataset)
        "is_new_to_dataset",  # Boolean: True if error is truly new (not in baseline, not in any other iteration)
        "introduced_in_this_iteration",  # Boolean: True if THIS specific iteration introduced this error
        "exists_in_iterations",  # String: Comma-separated iteration_ids where this error appears
        "first_seen_in"  # String: iteration_id or "baseline" where error first appeared
    ]

    @staticmethod
    def compute_oid(r: dict) -> str:
        """
        Stable hash-based OID:
        oid = sha1("filename|line_start|line_end")[:12]
        """
        base = f"{r['filename']}|{r['line_start']}|{r['line_end']}"
        full_hash = hashlib.sha1(base.encode("utf-8")).hexdigest()
        # return full_hash[:12]    # short version = readable + unique
        return full_hash

    @staticmethod
    def write_rows(rows, csv_path, iteration_id=None, original_problem_oid=None):
        if not rows:
            return

        enriched_rows = []
        for r in rows:
            oid = DiagnosticsWriter.compute_oid(r)
            # Add iteration_id and original_problem_oid to each row
            enriched_row = {
                "oid": oid, 
                "original_problem_oid": original_problem_oid,
                "iteration_id": iteration_id, 
                **r
            }
            enriched_rows.append(enriched_row)

        df = pd.DataFrame(enriched_rows, columns=DiagnosticsWriter.COLUMNS)

        file_exists = os.path.exists(csv_path)
        file_empty = (not file_exists) or os.path.getsize(csv_path) == 0

        df.to_csv(
            csv_path,
            mode="a",
            header=file_empty,
            index=False,
            encoding="utf-8"
        )

        print(f"[✓] Appended {len(rows)} rows to {csv_path}")
