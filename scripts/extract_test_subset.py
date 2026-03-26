import pandas as pd
import random
import os

def main():
    fixes_file = r"C:\Users\Admin\PycharmProjects\TFfixer\results\CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv"
    problems_file = r"c:\Users\Admin\PycharmProjects\TFRepair\problems\problems.csv"
    
    out_fixes = r"evaluation/data/test_subset_fixes.csv"
    out_problems = r"problems/test_subset_problems.csv"
    
    print(f"Loading Fixes: {fixes_file}")
    df_fixes = pd.read_csv(fixes_file)
    
    # 1. Get 5 unique random OIDs
    all_oids = df_fixes['oid'].dropna().unique().tolist()
    random.seed(42)
    selected_oids = random.sample(all_oids, 5)
    
    # 2. Filter fixes for these 5 OIDs
    subset_fixes = df_fixes[df_fixes['oid'].isin(selected_oids)]
    print(f"Fixes subset contains {len(subset_fixes)} rows.")
    subset_fixes.to_csv(out_fixes, index=False)
    
    # 3. Identify all corresponding projects for these fixes
    # Some older files might not have project_name, they might have repo_name
    proj_col = 'project_name' if 'project_name' in df_fixes.columns else 'repo_name'
    if proj_col not in df_fixes.columns:
        print("Could not find project_name column in fixes!")
        selected_projects = []
    else:
        selected_projects = subset_fixes[proj_col].dropna().unique().tolist()
    
    print(f"Selected Projects to capture baseline: {selected_projects}")
    
    # 4. Filter problems for ALL diagnostics occurring in these selected projects!
    print(f"Loading Problems: {problems_file}")
    df_problems = pd.read_csv(problems_file)
    
    proj_col_prob = 'project_name' if 'project_name' in df_problems.columns else 'repo_name'
    
    if selected_projects and proj_col_prob in df_problems.columns:
        subset_problems = df_problems[df_problems[proj_col_prob].isin(selected_projects)]
    else:
        print("Warning: Falling back to OID match because project names couldn't be resolved.")
        subset_problems = df_problems[df_problems['oid'].isin(selected_oids)]
        
    print(f"Problems subset contains {len(subset_problems)} rows (Full Project Baselines!)")
    subset_problems.to_csv(out_problems, index=False)
    
    print("\nSUCCESS! Subsets generated:")
    print(f" -> {out_fixes}")
    print(f" -> {out_problems}")

if __name__ == "__main__":
    main()
