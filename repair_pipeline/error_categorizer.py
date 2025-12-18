"""
Error Categorizer

Handles error categorization (baseline, cross-experiment, truly new) for the repair pipeline.
"""
import os
import pandas as pd


class ErrorCategorizer:
    """Categorizes errors based on baseline and cross-experiment tracking."""
    
    def __init__(self, clones_root="clones", problems_dataset=None, output_csv=None):
        """
        Initialize error categorizer.
        
        Args:
            clones_root: Root directory for cloned repositories
            problems_dataset: DataFrame with problem information (optional)
            output_csv: Path to diagnostics CSV for cross-experiment tracking
        """
        self.clones_root = clones_root
        self.problems = problems_dataset
        self.output_csv = output_csv
        
        # Cache for baseline errors (original errors before any fixes)
        self.baseline_errors_cache = {}  # {filename: [error_signatures]}
        
        # Cache for cross-experiment error tracking
        # Structure: {filename|iteration: {error_signature: {'first_iteration': str, 'iterations': [str]}}}
        self.experiment_errors_cache = {}
    
    def categorize_errors(self, extracted_rows, original_file, iteration_id, baseline_errors=None, original_problem_oid=None):
        """
        Categorize errors as baseline, cross-experiment, or truly new.
        
        Args:
            extracted_rows: List of error dictionaries to categorize
            original_file: Path to the file being evaluated
            iteration_id: Current iteration identifier
            baseline_errors: Set of baseline error signatures (optional, will be computed if None)
            original_problem_oid: Filter cross-experiment checks by specific problem OID (optional)
            
        Returns:
            list: Same extracted_rows with categorization fields added
        """
        # Get baseline errors if not provided
        if baseline_errors is None:
            baseline_errors = self.get_baseline_errors(original_file, project=None)
        
        # Load existing experiment errors for cross-experiment tracking
        existing_experiment_errors = self.get_existing_experiment_errors(
            original_file, 
            iteration_id, 
            original_problem_oid=original_problem_oid
        )
        
        for error in extracted_rows:
            # Create signature: use block_identifiers (stable) instead of line numbers
            block_id = error.get('block_identifiers', '')
            summary = error.get('summary', '')
            detail = error.get('detail', '')
            
            # Prefer block_identifiers, fallback to line
            if block_id:
                sig = f"{error.get('filename')}|{block_id}|{summary}|{detail}"
            else:
                sig = f"{error.get('filename')}|line_{error.get('line_start')}|{summary}|{detail}"
            
            # 3-WAY CHECK: baseline, existing experiments, or truly new
            if sig in baseline_errors:
                # Error existed in original file
                error['is_original_error'] = True
                error['is_new_error'] = False  # Deprecated, but keep for compatibility
                error['is_new_to_dataset'] = False
                error['introduced_in_this_iteration'] = False
                error['first_seen_in'] = 'baseline'
                error['exists_in_iterations'] = ''
                
            elif sig in existing_experiment_errors:
                # Error exists in other iterations (but not baseline)
                error['is_original_error'] = False
                error['is_new_error'] = True  # Deprecated - was "not in baseline"
                error['is_new_to_dataset'] = False  # Not new - exists in other experiments
                error['introduced_in_this_iteration'] = False  # Already exists elsewhere
                error['first_seen_in'] = existing_experiment_errors[sig]['first_iteration']
                error['exists_in_iterations'] = ','.join(existing_experiment_errors[sig]['iterations'])
                
            else:
                # Truly new error - never seen before
                error['is_original_error'] = False
                error['is_new_error'] = True  # Deprecated
                error['is_new_to_dataset'] = True  # TRULY NEW!
                error['introduced_in_this_iteration'] = True  # THIS iteration introduced it!
                error['first_seen_in'] = str(iteration_id) if iteration_id else 'unknown'
                error['exists_in_iterations'] = ''
        
        return extracted_rows
    
    def get_baseline_errors(self, original_file, project):
        """
        Get errors from problems.csv (baseline before any fixes).
        
        Args:
            original_file: Path to the file
            project: Project name (optional)
            
        Returns:
            set: Error signatures from baseline
        """
        # Check cache first
        if original_file in self.baseline_errors_cache:
            print(f"[BASELINE] Using cached baseline: {len(self.baseline_errors_cache[original_file])} original errors")
            return self.baseline_errors_cache[original_file]
        
        # If no problems dataset, return empty
        if self.problems is None:
            print(f"[BASELINE] No problems.csv provided - cannot determine baseline errors")
            self.baseline_errors_cache[original_file] = set()
            return set()
        
        # Use problems.csv to get baseline (much faster!)
        print(f"[BASELINE] Using problems.csv for baseline errors")
        
        # Filter problems for this file
        file_problems = self.problems[
            self.problems['filename'].str.contains(os.path.basename(original_file), na=False)
        ]
        
        # Create error signatures from problems.csv WITHOUT line numbers
        error_signatures = set()
        for _, problem in file_problems.iterrows():
            # problems.csv has: block_type + impacted_block_type (not block_identifiers!)
            block_type = problem.get('block_type', '')
            impacted_block_type = problem.get('impacted_block_type', '')
            
            # Combine to create block identifier
            if block_type and impacted_block_type:
                block_id = f"{block_type} {impacted_block_type}"
            elif impacted_block_type:
                block_id = impacted_block_type
            else:
                block_id = ''
            
            summary = problem.get('summary', '')
            detail = problem.get('detail', '')
            
            # Prefer block_identifiers over line numbers
            if block_id:
                sig = f"{problem.get('filename')}|{block_id}|{summary}|{detail}"
            else:
                # Fallback to line if no block identifier
                sig = f"{problem.get('filename')}|line_{problem.get('line_start')}|{summary}|{detail}"
            
            error_signatures.add(sig)
        
        print(f"[BASELINE] Found {len(error_signatures)} original errors from problems.csv")
        self.baseline_errors_cache[original_file] = error_signatures
        return error_signatures
    
    def get_existing_experiment_errors(self, filename, current_iteration_id, original_problem_oid=None):
        """
        Get errors from previous iterations (cross-experiment tracking).
        
        Args:
            filename: File to check
            current_iteration_id: Current iteration to exclude from check
            original_problem_oid: Filter by specific problem OID (optional, for tighter scoping)
            
        Returns:
            dict: {signature: {'first_iteration': str, 'iterations': [str]}}
        """
        # Check cache first
        cache_key = f"{filename}|{current_iteration_id}|{original_problem_oid}"
        if cache_key in self.experiment_errors_cache:
            print(f"[CROSS-EXP] Using cached experiment errors for {os.path.basename(filename)}")
            return self.experiment_errors_cache[cache_key]
        
        # Load existing diagnostics CSV if it exists
        if not self.output_csv or not os.path.exists(self.output_csv):
            print(f"[CROSS-EXP] No diagnostics CSV found - assuming first run")
            self.experiment_errors_cache[cache_key] = {}
            return {}
        
        print(f"[CROSS-EXP] Loading existing experiment errors from {self.output_csv}...")
        
        try:
            # Read diagnostics CSV
            diagnostics_df = pd.read_csv(self.output_csv)
            
            # Filter for this file, excluding current iteration
            condition = (
                (diagnostics_df['filename'].str.contains(os.path.basename(filename), na=False)) &
                (diagnostics_df['iteration_id'] != current_iteration_id)
            )
            
            # If OID provided, filter by it to scope 'existing' errors to this problem only
            if original_problem_oid:
                # Ensure we match string to string
                condition &= (diagnostics_df['original_problem_oid'].astype(str) == str(original_problem_oid))
                print(f"[CROSS-EXP] Filtering errors for Problem OID: {original_problem_oid}")
            
            file_diagnostics = diagnostics_df[condition]
            
            print(f"[CROSS-EXP] Found {len(file_diagnostics)} errors from other iterations")
            
            # Build signature -> iteration mapping
            experiment_errors = {}
            for _, error in file_diagnostics.iterrows():
                # Create same signature format as in get_baseline_errors
                block_id = error.get('block_identifiers', '')
                summary = error.get('summary', '')
                detail = error.get('detail', '')
                
                # Prefer block_identifiers over line numbers
                if block_id and pd.notna(block_id):
                    sig = f"{error.get('filename')}|{block_id}|{summary}|{detail}"
                else:
                    sig = f"{error.get('filename')}|line_{error.get('line_start')}|{summary}|{detail}"
                
                iteration = str(error.get('iteration_id', 'unknown'))
                
                # Track which iterations have this error
                if sig not in experiment_errors:
                    experiment_errors[sig] = {
                        'first_iteration': iteration,
                        'iterations': [iteration]
                    }
                else:
                    if iteration not in experiment_errors[sig]['iterations']:
                        experiment_errors[sig]['iterations'].append(iteration)
            
            print(f"[CROSS-EXP] Identified {len(experiment_errors)} unique error signatures from other experiments")
            
            # Cache and return
            self.experiment_errors_cache[cache_key] = experiment_errors
            return experiment_errors
            
        except Exception as e:
            print(f"[CROSS-EXP] Warning: Failed to load experiment errors: {e}")
            self.experiment_errors_cache[cache_key] = {}
            return {}
