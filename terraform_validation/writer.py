import os
import pandas as pd
import hashlib

class DiagnosticsWriter:
    """
    Writes diagnostic rows to CSV.
    Ensures that all columns required for parity with TFReproducer are preserved.
    """

    COLUMNS = [
        "project_name",
        "working_directory",
        "oid",
        "specific_oid",
        "original_problem_oid",
        "iteration_id",
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
        "block_type_full",
        "impacted_block_type",
        "impacted_block_start_line",
        "impacted_block_end_line",
        "impacted_block_content",
        "is_original_error",
        "is_new_error",
        "is_new_to_dataset",
        "introduced_in_this_iteration",
        "exists_in_iterations",
        "first_seen_in"
    ]

    @staticmethod
    def write_rows(rows, csv_path, iteration_id=None, original_problem_oid=None):
        """
        Appends diagnostic rows to a CSV file.
        
        Args:
            rows: List of diagnostic dictionaries
            csv_path: Path to the output CSV
            iteration_id: Optional iteration identifier
            original_problem_oid: Optional OID of original problem
        """
        if not rows:
            return

        enriched_rows = []
        for r in rows:
            # We preserve the OIDs computed by the Extractor (the source of truth)
            # but ensure iteration/original_oid are attached if provided.
            row_copy = r.copy()
            if iteration_id is not None:
                row_copy["iteration_id"] = iteration_id
            if original_problem_oid is not None:
                row_copy["original_problem_oid"] = original_problem_oid
                
            enriched_rows.append(row_copy)

        # Create DataFrame with explicit COLUMNS to ensure order and filtering
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
