"""
Validation Service

Handles Terraform validation and diagnostics extraction for the repair pipeline.
"""
import os
from terraform_validation.extractor import DiagnosticsExtractor
from terraform_validation.validator import TerraformValidator
from terraform_validation.writer import DiagnosticsWriter


class ValidationService:
    """Executes Terraform validation and extracts diagnostics."""
    
    def __init__(self, clones_root="clones", output_csv=None):
        """
        Initialize validation service.
        
        Args:
            clones_root: Root directory for cloned repositories
            output_csv: Path to output CSV for diagnostics
        """
        self.clones_root = clones_root
        self.output_csv = output_csv
    
    def validate_and_extract(self, original_file, project, iteration_id=None, original_problem_oid=None, write_to_csv=True):
        """
        Run terraform validate and extract diagnostics.
        
        Args:
            original_file: Path to the file being validated
            project: Project name
            iteration_id: Repair iteration identifier (optional)
            original_problem_oid: OID of original problem for linking (optional)
            write_to_csv: Whether to write diagnostics to CSV immediately (default: True)
            
        Returns:
            list: Extracted error dictionaries
        """
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
        
        # Write diagnostics to CSV if output path is provided AND requested
        if self.output_csv and extracted_rows and write_to_csv:
            print(f"Found {len(extracted_rows)} diagnostics.")
            DiagnosticsWriter.write_rows(
                extracted_rows, 
                self.output_csv, 
                iteration_id=iteration_id, 
                original_problem_oid=original_problem_oid
            )
        
        return extracted_rows
