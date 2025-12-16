# repair_driver.py
import os
import json
import pandas as pd

from repair_pipeline.apply_fix import FixApplier
from repair_pipeline.error_matcher import ErrorMatchingService
from terraform_validation.extractor import DiagnosticsExtractor
from terraform_validation.validator import TerraformValidator
from terraform_validation.writer import DiagnosticsWriter
from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer


class RepairEvaluator:

    def __init__(self, output_csv="repair_eval_diagnostics.csv", outcomes_csv="repair_outcomes.csv",
                 clones_root="clones", repair_mode="auto", problems_dataset=None, clear_existing=False):
        """
        This CSV will contain the diagnostics AFTER each LLM repair.
        And will follow the EXACT SAME format as DiagnosticsWriter.
        
        Args:
            output_csv: Path to diagnostics CSV file
            outcomes_csv: Path to outcomes/results CSV file
            clones_root: Root directory for cloned repositories
            repair_mode: "auto", "block", or "file"
            problems_dataset: Path to problems CSV (optional)
            clear_existing: If True, DELETE existing CSV files before starting (fresh run)
        """
        self.output_csv = output_csv
        self.clones_root = clones_root
        self.repair_mode = repair_mode
        self.problems = pd.read_csv(problems_dataset) if problems_dataset and os.path.exists(problems_dataset) else None
        self.error_matcher = ErrorMatchingService(line_tolerance=3)

        # Clear existing CSV files if requested (fresh start)
        if clear_existing:
            if os.path.exists(output_csv):
                os.remove(output_csv)
                print(f"[CLEAR] ✓ Deleted old diagnostics: {output_csv}")
            if os.path.exists(outcomes_csv):
                os.remove(outcomes_csv)
                print(f"[CLEAR] ✓ Deleted old outcomes: {outcomes_csv}")

        # Create empty CSV with headers if doesn't exist
        if not os.path.exists(output_csv):
            pd.DataFrame([], columns=DiagnosticsWriter.COLUMNS) \
                .to_csv(output_csv, index=False)

        self.outcomes_csv = outcomes_csv
        if not os.path.exists(self.outcomes_csv):
            pd.DataFrame([], columns=["oid", "iteration_id", "llm_name", "filename", "line_is_clean", 
                                      "specific_error_fixed", "new_error_count", "new_errors_in_file", "new_errors_in_module"]) \
                .to_csv(self.outcomes_csv, index=False)

    def _extract_project_name(self, row):
        """Extract project name from row, either directly or from filename."""
        if "project_name" in row:
            return row["project_name"]
        
        # Assumption: filename starts with clones/<project_name>/...
        parts = row["filename"].split("/")
        if len(parts) > 1 and parts[0] == "clones":
            return parts[1]
        
        return None
    
    def _get_original_file_path(self, filename):
        """Convert relative filename to absolute path."""
        relative_path = filename
        if relative_path.startswith("clones/"):
            relative_path = relative_path[len("clones/"):]
        
        return os.path.normpath(os.path.join(self.clones_root, relative_path))
    
    def _get_block_coordinates_from_problems(self, oid):
        """Get block coordinates from problems dataset by OID."""
        if self.problems is None or not oid:
            return None, None
        
        target_oid = str(oid)
        p_match = self.problems[self.problems["oid"].astype(str) == target_oid]
        
        if not p_match.empty:
            start = int(p_match.iloc[0]["impacted_block_start_line"])
            end = int(p_match.iloc[0]["impacted_block_end_line"])
            return start, end
        else:
            print(f"Warning: No match found in problems dataset for OID: {target_oid}")
            return None, None
    
    def _get_fix_content_and_coordinates(self, row):
        """Extract fix content and line coordinates based on repair mode."""
        fixed_content = None
        start_line = None
        end_line = None
        
        # Try full file fix first
        if "fixed_file" in row and pd.notna(row["fixed_file"]):
            if self.repair_mode == "file" or self.repair_mode == "auto":
                return row["fixed_file"], None, None
        
        # Otherwise, try block fix
        if self.repair_mode == "block" or self.repair_mode == "auto":
            fixed_content = row.get("fixed_block_content")
            if pd.isna(fixed_content):
                fixed_content = row.get("fixed_code")  # fallback
            
            # Get coordinates from problems dataset or fallback to row
            if "oid" in row and pd.notna(row["oid"]):
                start_line, end_line = self._get_block_coordinates_from_problems(row["oid"])
            
            # Fallback to row's own coordinates
            if start_line is None:
                start_line = int(row["line_start"]) if "line_start" in row and pd.notna(row["line_start"]) else None
            if end_line is None:
                end_line = int(row["line_end"]) if "line_end" in row and pd.notna(row["line_end"]) else None
        
        return fixed_content, start_line, end_line
    
    def _apply_and_validate(self, original_file, project, fixed_content, start_line, end_line, iteration_id):
        """Apply fix, run terraform validate, and extract diagnostics."""
        module_dir = os.path.dirname(original_file)
        
        # SAFEGUARD: Check for .bak files (should be ignored by Terraform)
        bak_files = [f for f in os.listdir(module_dir) if f.endswith('.bak')]
        if bak_files:
            print(f"[SAFEGUARD] Found {len(bak_files)} .bak backup file(s) - will be IGNORED by Terraform")
        
        # Run terraform validate
        print(f'[VALIDATE] Validating directory: {module_dir}')
        validation_result = TerraformValidator.validate(module_dir)
        
        # Debug: Check how many diagnostics terraform validate returned
        raw_diagnostics = validation_result.get("diagnostics", [])
        print(f"[DEBUG] Terraform validate returned {len(raw_diagnostics)} diagnostics")
        
        # SAFEGUARD: Verify no .bak files appear in diagnostics
        if raw_diagnostics:
            validated_files = set()
            for diag in raw_diagnostics:
                if isinstance(diag, dict) and "range" in diag:
                    filename = diag.get("range", {}).get("filename", "")
                    if filename:
                        validated_files.add(filename)
            
            # Check if any .bak files were validated (should NEVER happen)
            bak_validated = [f for f in validated_files if f.endswith('.bak')]
            if bak_validated:
                print(f"[ERROR] ❌ Terraform validated .bak files: {bak_validated}")
                print(f"[ERROR] This should NEVER happen - backup files should be ignored!")
            elif len(validated_files) > 0:
                print(f"[SAFEGUARD] ✓ Only .tf files validated: {sorted(validated_files)}")

        # Convert validation_result → diagnostics rows
        project_root = os.path.join(self.clones_root, project)
        print('project_root ', project_root)
        
        extracted_rows = DiagnosticsExtractor.extract_rows(
            project_name=project,
            result=validation_result,
            project_root=project_root
        )

        # Save diagnostics
        print(f"Found {len(extracted_rows)} diagnostics.")
        DiagnosticsWriter.write_rows(extracted_rows, self.output_csv, iteration_id=iteration_id)
        
        return extracted_rows
    
    def _calculate_error_metrics(self, extracted_rows, original_file):
        """Calculate error counts at different scopes."""
        original_file_normalized = os.path.normpath(original_file)
        
        errors_in_file = sum(
            1 for er in extracted_rows 
            if os.path.normpath(os.path.join(self.clones_root, er.get("filename", "").replace("clones/", ""))) == original_file_normalized
        )
        
        return {
            "total": len(extracted_rows),
            "in_file": errors_in_file,
            "in_module": len(extracted_rows)
        }
    
    def _evaluate_resolution_metrics(self, row, extracted_rows, start_line, end_line, fixed_file_content):
        """Evaluate whether the original error was resolved."""
        line_is_clean = None
        specific_error_fixed = None
        
        if self.problems is not None and "oid" in row:
            target_oid = str(row["oid"])
            p_match = self.problems[self.problems["oid"].astype(str) == target_oid]

            if not p_match.empty:
                # Prepare original error information
                try:
                    original_line = int(p_match.iloc[0].get("line_start", -1))
                except (ValueError, TypeError):
                    original_line = -1
                
                original_error_info = {
                    "summary": p_match.iloc[0].get("summary", ""),
                    "block_identifiers": str(p_match.iloc[0].get("block_identifiers", "")).strip(),
                    "line_start": original_line,
                    "impacted_block_start_line": p_match.iloc[0].get("impacted_block_start_line", -1),
                    "impacted_block_end_line": p_match.iloc[0].get("impacted_block_end_line", -1)
                }
                
                fix_context = {
                    "start_line": start_line,
                    "end_line": end_line,
                    "fixed_file_content": fixed_file_content
                }
                
                # Use ErrorMatchingService for evaluation
                line_is_clean = self.error_matcher.check_line_is_clean(
                    original_line, 
                    extracted_rows
                )
                
                specific_error_fixed = self.error_matcher.check_specific_error_fixed(
                    original_error_info,
                    extracted_rows,
                    fix_context
                )
        
        return {
            "line_is_clean": line_is_clean,
            "specific_error_fixed": specific_error_fixed
        }
    
    def _create_outcome_row(self, row, original_file, resolution_metrics, error_counts):
        """Create outcome row for CSV output."""
        # Convert to relative path
        try:
            relative_filename = os.path.relpath(original_file, os.getcwd())
            relative_filename = relative_filename.replace("\\", "/")
        except (ValueError, OSError):
            relative_filename = original_file
        
        return {
            "oid": row.get("oid", ""),
            "iteration_id": row.get("iteration_id", ""),
            "llm_name": row.get("llm_name", ""),
            "filename": relative_filename,
            "line_is_clean": resolution_metrics["line_is_clean"],
            "specific_error_fixed": resolution_metrics["specific_error_fixed"],
            "new_error_count": error_counts["total"],
            "new_errors_in_file": error_counts["in_file"],
            "new_errors_in_module": error_counts["in_module"]
        }
    
    def evaluate_repairs(self, llm_fixes_csv: str):
        df = pd.read_csv(llm_fixes_csv)

        for _, row in df.iterrows():
            # Extract project name
            project = self._extract_project_name(row)
            if not project:
                print(f"Skipping row, cannot determine project name: {row['filename']}")
                continue
            
            # Get file paths
            original_file = self._get_original_file_path(row["filename"])
            
            # Get fix content and coordinates
            fixed_file_content, start_line, end_line = self._get_fix_content_and_coordinates(row)

            if fixed_file_content is None or pd.isna(fixed_file_content):
                print(f"Skipping row, no fixed content found for: {original_file} (Mode: {self.repair_mode})")
                continue

            backup_path = FixApplier.apply_fix(
                original_file,
                fixed_file_content,
                start_line=start_line,
                end_line=end_line
            )

            # Apply fix, validate, and extract diagnostics
            extracted_rows = self._apply_and_validate(original_file, project, fixed_file_content, 
                                                      start_line, end_line, row.get("iteration_id"))

            # Calculate error counts
            error_counts = self._calculate_error_metrics(extracted_rows, original_file)
            print(f'[Metrics] Total errors: {error_counts["total"]}, File errors: {error_counts["in_file"]}, Module errors: {error_counts["in_module"]}')

            # Evaluate if error was resolved
            resolution_metrics = self._evaluate_resolution_metrics(
                row, extracted_rows, start_line, end_line, fixed_file_content
            )

            # Create and save outcome row
            outcome_row = self._create_outcome_row(row, original_file, resolution_metrics, error_counts)
            pd.DataFrame([outcome_row]).to_csv(self.outcomes_csv, mode='a', header=False, index=False)

            # Restore original file
            FixApplier.restore_original(original_file, backup_path)

