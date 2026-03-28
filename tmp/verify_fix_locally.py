import pandas as pd
import os
import sys

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from repair_pipeline.error_categorizer import ErrorCategorizer
from repair_pipeline.file_resolver import FileCoordinateResolver

# 1. Initialize Categorizer with your real data (pass as problems_dataset)
print("[1/3] Loading baseline data...")
baseline_df = pd.read_csv('problems/problems.csv')
ec = ErrorCategorizer(problems_dataset=baseline_df)

# 2. Load the \"Problematic\" Results (the ones currently showing 27 introduced errors)
print("[2/3] Loading current diagnostics results...")
results_file = 'llms_fixes_results/codellama_subset_20_new_diagnostics_after_validation.csv'
if not os.path.exists(results_file):
    print(f"ERROR: {results_file} not found locally.")
    sys.exit(1)

df = pd.read_csv(results_file)

# 3. Re-Categorize for symptomradar using the NEW Logic (911dc15)
project = 'futurice__symptomradar'
symptomradar_errors = df[df['project_name'] == project].to_dict('records')

if not symptomradar_errors:
    print(f"ERROR: No diagnostics found for {project} in {results_file}.")
    sys.exit(1)

print(f"[3/3] Re-categorizing {len(symptomradar_errors)} diagnostics for {project}...")
# This uses the new Project-Scoped and Text-Insensitive logic
# The original_file is where the fix was applied, but we now check the WHOLE project baseline.
categorized = ec.categorize_errors(
    symptomradar_errors, 
    original_file='clones/futurice__symptomradar/infra/modules/main/backend.tf',
    iteration_id="test",
    project=project
)

# 4. Final Audit
original = [e for e in categorized if e.get('is_original_error')]
introduced = [e for e in categorized if e.get('introduced_in_this_iteration')]

print("\n--- FINAL AUDIT RESULTS ---")
print(f"Total Diagnostics Found: {len(categorized)}")
print(f"Original Errors Found:   {len(original)}")
print(f"Introduced Errors:       {len(introduced)}")

if len(introduced) == 0:
    print("\n✅ SUCCESS: The 6/27 error count is RESOLVED.")
    print("All 27 diagnostics from the evaluation are now correctly recognized as Original errors.")
else:
    print(f"\n❌ STILL FAIL: {len(introduced)} errors are still unmatched.")
    # Print the first unmatched to debug why
    first = introduced[0]
    print(f"Sample Unmatched: {first.get('filename')} | {first.get('summary')}")
