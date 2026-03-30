"""
Error Categorizer

Handles error categorization (baseline, cross-experiment, truly new) for the repair pipeline.
"""
import os
import pandas as pd
from repair_pipeline.file_resolver import FileCoordinateResolver


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
        self.baseline_oids_cache = {}    # {filename: {oid}}
        self.baseline_specific_oids_cache = {} # {filename: {specific_oid}}
        
        # Cache for cross-experiment error tracking
        # Structure: {filename|iteration: {error_signature: {'first_iteration': str, 'iterations': [str]}}}
        self.experiment_errors_cache = {}
    
    def categorize_errors(
        self,
        extracted_rows,
        original_file,
        iteration_id,
        project=None,
        baseline_errors=None,
        original_problem_oid=None,
        original_problem_specific_oid=None,
    ):
        """
        Categorize errors as baseline, cross-experiment, or truly new.
        
        Args:
            extracted_rows: List of error dictionaries to categorize
            original_file: Path to the file being evaluated
            iteration_id: Current iteration identifier
            baseline_errors: Set of baseline error signatures (optional, will be computed if None)
            original_problem_oid: Filter cross-experiment checks by specific problem OID (optional)
            original_problem_specific_oid: Filter cross-experiment checks by specific diagnostic (optional)
            project: Project name for tighter baseline scoping (optional)
            
        Returns:
            list: Same extracted_rows with categorization fields added
        """
        # Get baseline errors and OIDs if not provided
        if baseline_errors is None:
            baseline_errors = self.get_baseline_errors(original_file, project=project)
        
        baseline_oids = self.baseline_oids_cache.get(f"{original_file}|{project}", set())
        baseline_specific_oids = self.baseline_specific_oids_cache.get(f"{original_file}|{project}", set())
        
        # Load existing experiment errors for cross-experiment tracking
        existing_experiment_errors = self.get_existing_experiment_errors(
            original_file, 
            iteration_id, 
            original_problem_oid=original_problem_oid,
            original_problem_specific_oid=original_problem_specific_oid,
        )
        for error in extracted_rows:
            from terraform_validation.extractor import DiagnosticsExtractor
            
            # Normalize fields for a stable signature that ignores line shifts and wording noise
            filename = FileCoordinateResolver.normalize_path(error.get('filename', ''))
            block_id = str(error.get('block_identifiers', '') or '').strip()
            summary = DiagnosticsExtractor.normalize_for_oid(error.get('summary', ''))
            
            # Stable signature: doesn't include detail/line_start to be resilient to changes
            stable_sig = f"{filename}|{block_id}|{summary}"
            
            # 3-WAY CHECK: baseline (by specific_oid, oid, or stable signature), existing experiments, or truly new
            is_originally_baseline = (
                (error.get('specific_oid') in baseline_specific_oids) or 
                (error.get('oid') in baseline_oids) or 
                (stable_sig in baseline_errors)
            )

            if is_originally_baseline:
                # Error existed in original file
                error['is_original_error'] = True
                error['is_new_error'] = False  # Deprecated, but keep for compatibility
                error['is_new_to_dataset'] = False
                error['introduced_in_this_iteration'] = False
                error['first_seen_in'] = 'baseline'
                error['exists_in_iterations'] = ''
                
            elif (stable_sig in existing_experiment_errors) or (error.get('specific_oid') in existing_experiment_errors):
                # Error exists in other iterations (but not baseline)
                error['is_original_error'] = False
                error['is_new_error'] = True  # Deprecated - was "not in baseline"
                error['is_new_to_dataset'] = False  # Not new - exists in other experiments
                
                # CRITICAL INDEPENDENCE FIX: Every iteration is an independent event!
                # If it's not in the baseline, THIS iteration introduced it, regardless 
                # of whether Iteration 1 also made the same mistake.
                error['introduced_in_this_iteration'] = True  
                
                # Get iteration info from cross-experiment cache
                exp_data = existing_experiment_errors.get(error.get('specific_oid')) or existing_experiment_errors.get(stable_sig)
                error['first_seen_in'] = exp_data['first_iteration']
                error['exists_in_iterations'] = ','.join(exp_data['iterations'])
                
            else:
                # Truly new error - never seen before
                error['is_original_error'] = False
                error['is_new_error'] = True  # Deprecated
                error['is_new_to_dataset'] = True  # TRULY NEW!
                error['introduced_in_this_iteration'] = True  # THIS iteration introduced it!
                error['first_seen_in'] = str(iteration_id) if iteration_id else 'unknown'
                error['exists_in_iterations'] = ''
        
        return extracted_rows
    
    def get_baseline_errors(self, original_file, project=None):
        """
        Get errors from problems.csv (baseline before any fixes).

        Signature format matches the live ``terraform validate`` output:
          ``filename | block_identifiers | summary | detail``

        Both the baseline (built here) and the post-fix errors (built in
        ``categorize_errors``) use exactly this format, so comparisons are valid.

        The filter is tightened when a ``project`` name is supplied:
          * primary: project_name + full filename  → unambiguous
          * fallback: basename only                → when project unknown

        Args:
            original_file: Absolute or relative path to the file being evaluated.
            project:       Project name (optional, improves precision).

        Returns:
            set: Error signatures from baseline.
        """
        cache_key = f"{original_file}|{project}"

        # Check cache first
        if cache_key in self.baseline_errors_cache:
            return self.baseline_errors_cache[cache_key]

        # If no problems dataset, return empty
        if self.problems is None:
            self.baseline_errors_cache[cache_key] = set()
            return set()


        # ------------------------------------------------------------------ #
        # Step 1 – filter problems to only those relevant to this scope       #
        #                                                                     #
        # If project is available, we load the ENTITY module/project context  #
        # because Terraform validation returns errors for the whole module.   #
        # ------------------------------------------------------------------ #
        has_project_col = 'project_name' in self.problems.columns
        basename = os.path.basename(original_file)
        norm_original = original_file.replace("\\", "/")

        def _full_path_match(prob_filename):
            rel = str(prob_filename).replace("\\", "/").lstrip("/")
            return norm_original.endswith(rel)

        if project and has_project_col:
            # BROAD SCOPE: load every error for the project
            project_mask = self.problems['project_name'].astype(str) == str(project)
            file_problems = self.problems[project_mask]
            
            # Fallback if project match returned nothing (unlikely but safe)
            if file_problems.empty:
                file_problems = self.problems[self.problems['filename'].apply(_full_path_match)]
        else:
            # NARROW SCOPE: load only for this specific file
            file_problems = self.problems[self.problems['filename'].apply(_full_path_match)]
            if file_problems.empty:
                file_problems = self.problems[self.problems['filename'].str.contains(basename, na=False, regex=False)]

        # ------------------------------------------------------------------ #
        # Step 2 – build signatures  (must match categorize_errors format)   #
        # ------------------------------------------------------------------ #
        from terraform_validation.extractor import DiagnosticsExtractor
        
        error_signatures = set()
        baseline_oids = set()
        baseline_specific_oids = set()
        
        for _, problem in file_problems.iterrows():
            # Robust normalization for signature
            filename = FileCoordinateResolver.normalize_path(problem.get('filename', ''))
            block_id = str(problem.get('block_identifiers', '') or '').strip()
            summary  = DiagnosticsExtractor.normalize_for_oid(problem.get('summary', ''))

            # Signature excludes detail/line_start for stability
            stable_sig = f"{filename}|{block_id}|{summary}"
            error_signatures.add(stable_sig)
            
            # Track OIDs and specific_oids for exact/content matching
            p_oid = problem.get('oid')
            p_spec_oid = problem.get('specific_oid')
            if p_oid: 
                baseline_oids.add(str(p_oid).strip())
            if p_spec_oid: 
                baseline_specific_oids.add(str(p_spec_oid).strip())

        # Update caches
        self.baseline_errors_cache[cache_key] = error_signatures
        self.baseline_oids_cache[cache_key] = baseline_oids
        self.baseline_specific_oids_cache[cache_key] = baseline_specific_oids
        
        return error_signatures
    
    def get_existing_experiment_errors(
        self,
        filename,
        current_iteration_id,
        original_problem_oid=None,
        original_problem_specific_oid=None,
    ):
        """
        Get errors from previous iterations (cross-experiment tracking).
        
        Args:
            filename: File to check
            current_iteration_id: Current iteration to exclude from check
            original_problem_oid: Filter by specific problem OID (optional, for tighter scoping)
            original_problem_specific_oid: Filter by specific diagnostic (optional, highest fidelity)
            
        Returns:
            dict: {signature: {'first_iteration': str, 'iterations': [str]}}
        """
        # Check cache first
        cache_key = f"{filename}|{current_iteration_id}|{original_problem_oid}|{original_problem_specific_oid}"
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
            # Prefer specific_oid scoping when available because location-oids can collide.
            if original_problem_specific_oid and 'original_problem_specific_oid' in diagnostics_df.columns:
                condition &= (
                    diagnostics_df['original_problem_specific_oid'].astype(str)
                    == str(original_problem_specific_oid)
                )
                print(f"[CROSS-EXP] Filtering errors for Problem specific_oid: {original_problem_specific_oid}")
            elif original_problem_oid and 'original_problem_oid' in diagnostics_df.columns:
                # Ensure we match string to string
                condition &= (diagnostics_df['original_problem_oid'].astype(str) == str(original_problem_oid))
                print(f"[CROSS-EXP] Filtering errors for Problem OID: {original_problem_oid}")
            
            file_diagnostics = diagnostics_df[condition]
            
            print(f"[CROSS-EXP] Found {len(file_diagnostics)} errors from other iterations")
            
            # Build signature -> iteration mapping
            experiment_errors = {}
            for _, error in file_diagnostics.iterrows():
                # Create same signature format as in get_baseline_errors
                filename = FileCoordinateResolver.normalize_path(error.get('filename', ''))
                block_id = str(error.get('block_identifiers', '') or '').strip()
                summary = str(error.get('summary', '') or '').strip()
                detail = str(error.get('detail', '') or '').strip()
                
                # Prefer block_identifiers over line numbers
                if block_id:
                    sig = f"{filename}|{block_id}|{summary}|{detail}"
                else:
                    sig = f"{filename}|line_{error.get('line_start')}|{summary}|{detail}"
                
                # Use specific_oid as primary key for iteration cross-tracking if available
                sig_key = error.get('specific_oid') or sig
                
                iteration = str(error.get('iteration_id', 'unknown'))
                
                # Track which iterations have this error
                if sig_key not in experiment_errors:
                    experiment_errors[sig_key] = {
                        'first_iteration': iteration,
                        'iterations': [iteration]
                    }
                else:
                    if iteration not in experiment_errors[sig_key]['iterations']:
                        experiment_errors[sig_key]['iterations'].append(iteration)
            
            print(f"[CROSS-EXP] Identified {len(experiment_errors)} unique error signatures from other experiments")
            
            # Cache and return
            self.experiment_errors_cache[cache_key] = experiment_errors
            return experiment_errors
            
        except Exception as e:
            print(f"[CROSS-EXP] Warning: Failed to load experiment errors: {e}")
            self.experiment_errors_cache[cache_key] = {}
            return {}
