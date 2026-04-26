import pandas as pd
import numpy as np
import argparse
import os


def pass_at_k(n, c, k):
    """
    Unbiased estimator for pass@k. 
    """
    if n - c < k:
        return 1.0

    prob_all_fail = 1.0
    for i in range(k):
        prob_all_fail *= (n - c - i) / (n - i)

    return 1.0 - prob_all_fail


def main():
    parser = argparse.ArgumentParser(description="Calculate pass@k metric with strict validation and scope-split")
    parser.add_argument("--problems-csv", required=True, help="Path to problems CSV")
    parser.add_argument("--fixes-csv", required=True, help="Path to fixes/outcomes CSV")
    parser.add_argument("--k-values", nargs="+", type=int, default=[1, 5, 10], help="Values of k")
    parser.add_argument("--save-to", help="Optional path to save results")
    args = parser.parse_args()

    try:
        problems_df = pd.read_csv(args.problems_csv)
        fixes_df = pd.read_csv(args.fixes_csv)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # HARDENING Improvement A: Enforce one row = one candidate attempt
    if 'oid' in fixes_df.columns and 'iteration_id' in fixes_df.columns:
        dups = fixes_df.duplicated(subset=['oid', 'iteration_id'], keep=False)
        if dups.any():
            print(f"WARNING: {dups.sum()} duplicate (oid, iteration_id) rows detected. Keeping only the first occurrence.")
            fixes_df = fixes_df.drop_duplicates(subset=['oid', 'iteration_id'], keep='first')

    # Ensure OIDs in fixes exist in problems
    valid_oids = set(problems_df['oid'])
    fixes_df = fixes_df[fixes_df['oid'].isin(valid_oids)]

    # Map column names - repair_driver uses prefixed names
    if 'line_specific_error_fixed' in fixes_df.columns and 'specific_error_fixed' not in fixes_df.columns:
        fixes_df['specific_error_fixed'] = fixes_df['line_specific_error_fixed']
    if 'module_fix_introduced_errors' in fixes_df.columns and 'introduced_this_iteration' not in fixes_df.columns:
        fixes_df['introduced_this_iteration'] = fixes_df['module_fix_introduced_errors']

    # HARDENING Improvement B: Handle booleans and NaNs safely
    if 'specific_error_fixed' in fixes_df.columns:
        fixes_df['specific_error_fixed'] = fixes_df['specific_error_fixed'].fillna(False).astype(bool)
    if 'introduced_this_iteration' in fixes_df.columns:
        fixes_df['introduced_this_iteration'] = fixes_df['introduced_this_iteration'].fillna(0).astype(int)
    if 'block_fix_introduced_errors' in fixes_df.columns:
        fixes_df['block_fix_introduced_errors'] = fixes_df['block_fix_introduced_errors'].fillna(0).astype(int)

    # SUCCESS AGGREGATION
    group_cols = ['oid']
    if 'specific_error_fixed' not in fixes_df.columns:
        print("Error: Required column 'specific_error_fixed' missing for evaluation.")
        return

    stats = fixes_df.groupby(group_cols)['specific_error_fixed'].agg(['count', 'sum']).reset_index()
    stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
    
    # SCOPE-SEPARATED METRICS (Improvement E)
    # 1. Block-Level
    if 'block_fix_introduced_errors' in fixes_df.columns:
        fixes_df['block_strict_success'] = fixes_df['specific_error_fixed'] & (fixes_df['block_fix_introduced_errors'] == 0)
    else:
        fixes_df['block_strict_success'] = fixes_df['specific_error_fixed'] # Fallback
            
    # 2. Module-Level (Standard strict)
    if 'introduced_this_iteration' in fixes_df.columns:
        fixes_df['module_strict_success'] = fixes_df['specific_error_fixed'] & (fixes_df['introduced_this_iteration'] == 0)
    else:
        fixes_df['module_strict_success'] = fixes_df['block_strict_success'] # Fallback
            
    # Regression Rates
    block_reg_rate = (fixes_df['block_fix_introduced_errors'] > 0).mean() if 'block_fix_introduced_errors' in fixes_df.columns else 0.0
    module_reg_rate = (fixes_df['introduced_this_iteration'] > 0).mean() if 'introduced_this_iteration' in fixes_df.columns else 0.0

    # Grouping
    block_strict_stats = fixes_df.groupby(group_cols)['block_strict_success'].agg(['count', 'sum']).reset_index()
    block_strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
    
    module_strict_stats = fixes_df.groupby(group_cols)['module_strict_success'].agg(['count', 'sum']).reset_index()
    module_strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)

    # HARDENING Improvement D: Warn when k > n for many problems
    print("\n--- SAMPLE SIZE VALIDATION ---")
    for k in args.k_values:
        underpowered = stats[stats['n'] < k]
        if not underpowered.empty:
            pct = (len(underpowered) / len(stats)) * 100
            print(f"WARNING: {pct:.1f}% of problems ({len(underpowered)}/{len(stats)}) have fewer than {k} samples. pass@{k} estimates may be mathematically awkward.")

    # COMPUTE PASS@K
    results = []
    model_name = os.path.basename(args.fixes_csv)
    row = {"LLM": model_name}
    
    for k in args.k_values:
        scores = stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"pass@{k}"] = scores.mean()
        
        b_scores = block_strict_stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"block_strict_pass@{k}"] = b_scores.mean()
        
        m_scores = module_strict_stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"module_strict_pass@{k}"] = m_scores.mean()
            
    row["Block_Reg_Rate"] = block_reg_rate
    row["Module_Reg_Rate"] = module_reg_rate
        
    results_df = pd.DataFrame([row])
    print("\n--- FINAL SCOPE-SEPARATED RESULTS (OUTDATED SCRIPT) ---")
    print(results_df.to_string(index=False))

    if args.save_to:
        os.makedirs(os.path.dirname(args.save_to), exist_ok=True)
        results_df.to_csv(args.save_to, index=False)
        print(f"Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
