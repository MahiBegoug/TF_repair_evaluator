import os
import sys
import pandas as pd

# Add the project root to sys.path
sys.path.append(os.getcwd())

from repair_pipeline.error_categorizer import ErrorCategorizer
from repair_pipeline.file_resolver import FileCoordinateResolver

def test_signature_parity():
    # 1. Mock a baseline problem with a non-standard path (like what might be in problems.csv)
    baseline_path = "../../clones/futurice__symptomradar/infra/modules/main/backend.tf"
    problem_data = {
        'project_name': 'futurice__symptomradar',
        'filename': baseline_path,
        'block_identifiers': 'resource backend',
        'summary': 'Argument is deprecated',
        'detail': 'Use auto instead.',
        'line_start': 10,
        'oid': '270eaf2cba06',
        'specific_oid': '7fab63fb29c8'
    }
    
    problems_df = pd.DataFrame([problem_data])
    
    # 2. Mock a runtime diagnostic found on Linux (standardized path)
    runtime_path = "clones/futurice__symptomradar/infra/modules/main/backend.tf"
    diagnostic = {
        'filename': runtime_path,
        'block_identifiers': 'resource backend',
        'summary': 'Argument is deprecated',
        'detail': 'Use auto instead.',
        'line_start': 10
    }
    
    # 3. Create ErrorCategorizer
    cat = ErrorCategorizer(problems_dataset=problems_df)
    
    # 4. Check categorization
    # This will trigger get_baseline_errors which builds the cache using normalize_path
    cat.categorize_errors(
        [diagnostic], 
        original_file=runtime_path, 
        project='futurice__symptomradar',
        iteration_id=1
    )
    
    is_original = diagnostic.get('is_original_error', False)
    
    print(f"Baseline Path: {baseline_path}")
    print(f"Runtime Path:  {runtime_path}")
    print(f"Categorized as Original Error: {is_original}")
    
    if is_original:
        print("VERIFICATION SUCCESS: Signatures match despite path differences.")
    else:
        print("VERIFICATION FAILED: Signature mismatch remains.")

if __name__ == "__main__":
    test_signature_parity()
