# repair_driver.py
import os
import json
import pandas as pd

from repair_pipeline.apply_fix import FixApplier
# from apply_fix import FixApplier
from terraform_validation.extractor import DiagnosticsExtractor
from terraform_validation.validator import TerraformValidator
from terraform_validation.writer import DiagnosticsWriter


class RepairEvaluator:

    def __init__(self, output_csv="repair_eval_diagnostics.csv", outcomes_csv="repair_outcomes.csv", clones_root="clones"):
        """
        This CSV will contain the diagnostics AFTER each LLM repair.
        And will follow the EXACT SAME format as DiagnosticsWriter.
        """
        self.output_csv = output_csv
        self.clones_root = clones_root

        if not os.path.exists(output_csv):
            # create empty file with header
            pd.DataFrame([], columns=DiagnosticsWriter.COLUMNS) \
                .to_csv(output_csv, index=False)

        self.outcomes_csv = outcomes_csv
        if not os.path.exists(self.outcomes_csv):
            pd.DataFrame([], columns=["oid", "iteration_id", "llm_name", "filename", "plausible_fix"]) \
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
            
            original_file = os.path.join(self.clones_root, relative_path)
            fixed_file = row["fixed_file"]
            
            if not os.path.exists(original_file):
                print(f"Error: File not found: {original_file}")
                continue

            module_dir = os.path.dirname(original_file)

            print(f"\n=== Testing fix for file: {original_file} ===")

            print('project_root ::')

            # 1. Apply LLM fix
            backup_path = FixApplier.apply_fix(original_file, fixed_file)

            # 2. Run terraform validate
            validation_result = TerraformValidator.validate(module_dir)

            # 3. Convert validation_result → diagnostics rows (same logic as initial extraction)
            project_root = os.path.join(self.clones_root, project)

            extracted_rows = DiagnosticsExtractor.extract_rows(
                project_name=project,
                result=validation_result,
                project_root=project_root
            )

            # 4. Save diagnostics using DiagnosticsWriter (same hashing, same schema)
            print(f"Found {len(extracted_rows)} diagnostics.")
            DiagnosticsWriter.write_rows(extracted_rows, self.output_csv)

            # 5. Log outcome
            is_plausible = len(extracted_rows) == 0
            outcome_row = {
                "oid": row.get("oid", ""),
                "iteration_id": row.get("iteration_id", ""),
                "llm_name": row.get("llm_name", ""),
                "filename": original_file,
                "plausible_fix": is_plausible
            }
            pd.DataFrame([outcome_row]).to_csv(self.outcomes_csv, mode='a', header=False, index=False)

            # 6. Restore original file
            FixApplier.restore_original(original_file, backup_path)
