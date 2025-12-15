# repair_driver.py
import os
import json
import pandas as pd

from repair_pipeline.apply_fix import FixApplier
# from apply_fix import FixApplier
from terraform_validation.extractor import DiagnosticsExtractor
from terraform_validation.validator import TerraformValidator
from terraform_validation.writer import DiagnosticsWriter
from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer


class RepairEvaluator:

    def __init__(self, output_csv="repair_eval_diagnostics.csv", outcomes_csv="repair_outcomes.csv",
                 clones_root="clones", repair_mode="auto", problems_dataset=None):
        """
        This CSV will contain the diagnostics AFTER each LLM repair.
        And will follow the EXACT SAME format as DiagnosticsWriter.
        repair_mode: "auto", "block", "file"
        """
        self.output_csv = output_csv
        self.clones_root = clones_root
        self.repair_mode = repair_mode
        self.problems = pd.read_csv(problems_dataset) if problems_dataset and os.path.exists(problems_dataset) else None

        if not os.path.exists(output_csv):
            # create empty file with header
            pd.DataFrame([], columns=DiagnosticsWriter.COLUMNS) \
                .to_csv(output_csv, index=False)

        self.outcomes_csv = outcomes_csv
        if not os.path.exists(self.outcomes_csv):
            pd.DataFrame([], columns=["oid", "iteration_id", "llm_name", "filename", "resolved_original", 
                                      "new_error_count", "new_errors_in_file", "new_errors_in_module"]) \
                .to_csv(self.outcomes_csv, index=False)

    def evaluate_repairs(self, llm_fixes_csv: str):
        df = pd.read_csv(llm_fixes_csv)

        for _, row in df.iterrows():
            # Extract project name from filename if not present
            if "project_name" not in row:
                # Assumption: filename starts with clones/<project_name>/...
                parts = row["filename"].split("/")
                if len(parts) > 1 and parts[0] == "clones":
                    project = parts[1]
                else:
                    # Fallback or error handling
                    print(f"Skipping row, cannot determine project name: {row['filename']}")
                    continue
            else:
                project = row["project_name"]

            # Construct absolute path to the original file
            # Remove 'clones/' prefix from filename to append to clones_root
            relative_path = row["filename"]
            if relative_path.startswith("clones/"):
                relative_path = relative_path[len("clones/"):]

            # Normalize path to convert forward slashes to OS-native separators
            original_file = os.path.normpath(os.path.join(self.clones_root, relative_path))
            # 1. Apply LLM fix
            # Support both full file (fixed_file) and block partial (fixed_block_content)

            fixed_file_content = None
            start_line = None
            end_line = None

            # Helper to extract block info
            def extract_block_info(r):
                content = r.get("fixed_block_content")
                if pd.isna(content):
                    content = r.get("fixed_code")  # fallback

                # Check problems dataset for impacted block coordinates
                s = None
                e = None

                if self.problems is not None:
                    # Match by OID (unique identifier for the problem instance)
                    # Use string comparison to avoid type mismatches

                    if "oid" in r and pd.notna(r["oid"]):
                        target_oid = str(r["oid"])

                        # Ensure problems OID column is also treated as string
                        # Optimally, we should enforce this at load time, but explicit conversion here is safer

                        # We use .astype(str) on the column for comparison
                        p_match = self.problems[self.problems["oid"].astype(str) == target_oid]

                        if not p_match.empty:
                            # Use the impacted block coordinates!
                            s = int(p_match.iloc[0]["impacted_block_start_line"])
                            e = int(p_match.iloc[0]["impacted_block_end_line"])
                            # print(f"  Mapped coordinates (OID={target_oid}) to impacted block: {s}-{e}")
                        else:
                            print(f"Warning: No match found in problems dataset for OID: {target_oid}")
                    else:
                        print("Warning: Row missing OID, cannot map to impacted block coordinates.")

                # Fallback to row's own coordinates if no match or problems not loaded
                if s is None:
                    s = int(r["line_start"]) if "line_start" in r and pd.notna(r["line_start"]) else None
                if e is None:
                    e = int(r["line_end"]) if "line_end" in r and pd.notna(r["line_end"]) else None

                return content, s, e

            if self.repair_mode == "file":
                if "fixed_file" in row and pd.notna(row["fixed_file"]):
                    fixed_file_content = row["fixed_file"]
            elif self.repair_mode == "block":
                fixed_file_content, start_line, end_line = extract_block_info(row)
            else:  # auto
                if "fixed_file" in row and pd.notna(row["fixed_file"]):
                    fixed_file_content = row["fixed_file"]
                else:
                    fixed_file_content, start_line, end_line = extract_block_info(row)

            if fixed_file_content is None or pd.isna(fixed_file_content):
                print(f"Skipping row, no fixed content found for: {original_file} (Mode: {self.repair_mode})")
                continue

            backup_path = FixApplier.apply_fix(
                original_file,
                fixed_file_content,
                start_line=start_line,
                end_line=end_line
            )

            # 2. Run terraform validate
            module_dir = os.path.dirname(original_file)
            print('module_dir ', module_dir)
            validation_result = TerraformValidator.validate(module_dir)
            
            # Debug: Check how many diagnostics terraform validate returned
            raw_diagnostics = validation_result.get("diagnostics", [])
            print(f"[DEBUG] Terraform validate returned {len(raw_diagnostics)} diagnostics")

            # 3. Convert validation_result → diagnostics rows (same logic as initial extraction)
            project_root = os.path.join(self.clones_root, project)

            print('project_root ', project_root)
            extracted_rows = DiagnosticsExtractor.extract_rows(
                project_name=project,
                result=validation_result,
                project_root=project_root
            )

            # 4. Save diagnostics using DiagnosticsWriter (same hashing, same schema)
            print(f"Found {len(extracted_rows)} diagnostics.")
            # Include iteration_id to track which repair iteration generated these diagnostics

            # break

            iteration_id = row.get("iteration_id", None)
            DiagnosticsWriter.write_rows(extracted_rows, self.output_csv, iteration_id=iteration_id)

            # 5. Log outcome and calculate error metrics
            # is_plausible = len(extracted_rows) == 0

            resolved_original = None
            new_error_count = len(extracted_rows)  # Total errors (legacy)
            
            # Calculate file-level errors (errors in the modified file only)
            # Normalize original_file path for comparison
            original_file_normalized = os.path.normpath(original_file)
            new_errors_in_file = sum(1 for er in extracted_rows 
                                     if os.path.normpath(os.path.join(self.clones_root, er.get("filename", "").replace("clones/", ""))) == original_file_normalized)
            
            # All errors in extracted_rows are module-level (from the validated module)
            new_errors_in_module = len(extracted_rows)
            
            print(f'[Metrics] Total errors: {new_error_count}, File errors: {new_errors_in_file}, Module errors: {new_errors_in_module}')

            if self.problems is not None and "oid" in row:
                target_oid = str(row["oid"])
                p_match = self.problems[self.problems["oid"].astype(str) == target_oid]

                if not p_match.empty:
                    original_summary = p_match.iloc[0].get("summary", "")
                    original_identifiers = str(p_match.iloc[0].get("block_identifiers", "")).strip()

                    # Heuristic: The original error is "resolved" if NO diagnostic in the new set 
                    # matches the original summary AND the specific block identifiers.

                    found_original = False
                    for er in extracted_rows:
                        # 1. Check if Identifiers match (Strongest check)
                        current_identifiers = str(er.get("block_identifiers", "")).strip()

                        # If we have identifiers from both sides, compare them.
                        if original_identifiers and current_identifiers:
                            is_same_block = (original_identifiers == current_identifiers)
                        else:
                            is_same_block = False

                        if is_same_block:
                            # Check if summary matches
                            if er.get("summary") == original_summary:
                                # Reinforce by checking positional alignment
                                # This ensures the error is in roughly the same location
                                position_matches = True

                                if start_line is not None and "line_start" in er:
                                    try:
                                        er_line = int(er.get("line_start", -1))
                                        original_line = int(p_match.iloc[0].get("line_start", -1)) if "line_start" in \
                                                                                                      p_match.iloc[
                                                                                                          0] else -1

                                        # Allow some tolerance for line number shifts due to fix
                                        if er_line != -1 and original_line != -1:
                                            line_diff = abs(er_line - original_line)
                                            # If lines differ by more than 5, likely different error
                                            if line_diff > 3:
                                                position_matches = False
                                    except (ValueError, TypeError):
                                        # If we can't parse line numbers, rely on identifier match
                                        pass

                                if position_matches:
                                    found_original = True
                                    break
                        else:
                            # Identifier Mismatch? Check fallback logic for safety
                            # (e.g. parser failed to get ID but line matches).
                            # Only use fallback if current_identifiers is EMPTY (parser failure).
                            if not current_identifiers:
                                # Fallback to positional check logic
                                if fixed_file_content:
                                    new_lines_count = len(fixed_file_content.splitlines())
                                else:
                                    new_lines_count = 0
                                buffer = 2
                                check_start = (start_line if start_line else 1) - buffer
                                check_end = (start_line if start_line else 1) + new_lines_count + buffer

                                try:
                                    er_line = int(er.get("line_start", -1))
                                except:
                                    er_line = -1

                                if er_line != -1 and check_start <= er_line <= check_end:
                                    if er.get("summary") == original_summary:
                                        found_original = True
                                        break
                            elif original_identifiers and current_identifiers:
                                # Both identifiers exist but don't match
                                # This handles renamed blocks (e.g., kubernetes_namespace → kubernetes_namespace_v1)
                                # Check if error is in the same position as the fix (same block, just renamed)
                                if start_line is not None and end_line is not None:
                                    try:
                                        er_line = int(er.get("line_start", -1))
                                        original_block_start = int(p_match.iloc[0].get("impacted_block_start_line", -1))
                                        original_block_end = int(p_match.iloc[0].get("impacted_block_end_line", -1))

                                        # Check if the new error falls within the original block's position range
                                        # Allow small buffer for line shifts
                                        buffer = 3
                                        if (er_line != -1 and original_block_start != -1 and
                                                original_block_start - buffer <= er_line <= original_block_end + buffer):
                                            # Error is in the same positional area as the fixed block
                                            if er.get("summary") == original_summary:
                                                # Same error in same position but different identifier = renamed block
                                                found_original = True
                                                break
                                    except (ValueError, TypeError, KeyError):
                                        # Can't determine position, skip this check
                                        pass

                    resolved_original = not found_original

            # Convert absolute path to relative path from current working directory
            # This preserves the clones_dir configuration (e.g., ../TFReproducer/clones/...)
            try:
                relative_filename = os.path.relpath(original_file, os.getcwd())
                # Normalize to forward slashes for consistency across platforms
                relative_filename = relative_filename.replace("\\", "/")
            except (ValueError, OSError):
                # If relpath fails (e.g., different drives on Windows), use absolute path
                relative_filename = original_file
            
            outcome_row = {
                "oid": row.get("oid", ""),
                "iteration_id": row.get("iteration_id", ""),
                "llm_name": row.get("llm_name", ""),
                "filename": relative_filename,
                # "plausible_fix": is_plausible,
                "resolved_original": resolved_original,
                "new_error_count": new_error_count,
                "new_errors_in_file": new_errors_in_file,
                "new_errors_in_module": new_errors_in_module
            }
            # Append to CSV with new columns (might need header update if file exists, 
            # but append mode without header assumes consistent schema. 
            # If schema changes, we might need to recreate the file or handle it.)

            # To be safe, we should update outcomes_csv initialization to include these columns 
            # or just rely on pandas to handle it if we rewrite/append correctly.
            # But append mode 'a' with header=False relies on existing columns.
            # We need to update the __init__ to include these columns in the empty file creation.

            pd.DataFrame([outcome_row]).to_csv(self.outcomes_csv, mode='a', header=False, index=False)

            # 6. Restore original file
            FixApplier.restore_original(original_file, backup_path)
