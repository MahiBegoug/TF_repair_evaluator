import pandas as pd
import json

# 1. Load result files
diagnostics_df = pd.read_csv('llms_fixes_results/codellama_subset_20_new_diagnostics_after_validation.csv')
problems_df = pd.read_csv('problems/problems.csv')

# 2. Filter for our suspect OID
subset = diagnostics_df[diagnostics_df['oid'] == '270eaf2cba06']
introduced = subset[subset['is_original_error'] == False]

print(f"Total Found: {len(subset)}")
print(f"Marked as Introduced: {len(introduced)}")

if len(introduced) > 0:
    print("\nSuspect Introduced Errors (Top 6):")
    print(introduced[['filename', 'summary', 'specific_oid']].head(6).to_string())
    
    # Check if these specific_oids exist in baseline (even if filename mismatched)
    print("\nDo these specific_oids exist ANYWHERE in the baseline for this project?")
    baseline_project = problems_df[problems_df['project_name'] == 'futurice__symptomradar']
    for row_idx, row in introduced.iterrows():
        soid = row['specific_oid']
        match = baseline_project[baseline_project['specific_oid'] == soid]
        if not match.empty:
            print(f"  - OID {soid}: FOUND IN BASELINE (recorded as {match.iloc[0]['filename']})")
        else:
            # Fallback signature check: check manually generated signature
            print(f"  - OID {soid}: NOT IN BASELINE (by SOID)")
