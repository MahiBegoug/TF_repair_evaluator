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
    parser = argparse.ArgumentParser(description="Calculate pass@k metric")
    parser.add_argument("--problems-csv", required=True, help="Path to problems CSV (oid, filename)")
    parser.add_argument("--fixes-csv", required=True, help="Path to fixes CSV (oid, iteration_id, plausible_fix)")
    parser.add_argument("--k-values", nargs="+", type=int, default=[1, 5, 10], help="Values of k to calculate")
    parser.add_argument("--save-to", help="Optional path to save the results CSV")
    args = parser.parse_args()

    try:
        problems_df = pd.read_csv(args.problems_csv)
        fixes_df = pd.read_csv(args.fixes_csv)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Calculate success per (oid, iteration_id)
    # Success means the oid is NOT present as an 'is_original_error' in that iteration.
    
    # Get all (oid, iteration) pairs that SHOULD exist
    all_oids = problems_df['oid'].unique()
    # Find max iteration from fixes_df
    num_iterations = fixes_df['iteration_id'].max()
    if pd.isna(num_iterations):
        num_iterations = 0
    else:
        num_iterations = int(num_iterations)

    rows = []
    for oid in all_oids:
        for it in range(1, num_iterations + 1):
            # Check if this OID still exists as an original error in this iteration
            is_fixed = not ((fixes_df['oid'] == oid) & 
                           (fixes_df['iteration_id'] == it) & 
                           (fixes_df['is_original_error'] == True)).any()
            
            # Check for regressions (any new error introduced in this iteration for THIS project/module)
            # Actually, regressions are usually tracked per-iteration globally for the fix attempt.
            # If ANY new error exists in this iteration for the target file, it's a regression.
            has_regression = ((fixes_df['iteration_id'] == it) & 
                             (fixes_df['is_new_error'] == True)).any()
            
            rows.append({
                'oid': oid,
                'iteration_id': it,
                'is_fixed': is_fixed,
                'strict_success': is_fixed and not has_regression
            })
    
    analysis_df = pd.DataFrame(rows)
    
    # Group by OID to get n and c for pass@k
    stats = analysis_df.groupby('oid')['is_fixed'].agg(['count', 'sum']).reset_index()
    stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
    
    strict_stats = analysis_df.groupby('oid')['strict_success'].agg(['count', 'sum']).reset_index()
    strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)

    results = []
    model_name = os.path.basename(args.fixes_csv).replace("_synthetic_fixes.csv", "").replace("_fixes.csv", "")
    row = {"LLM": model_name}
    
    for k in args.k_values:
        # pass@k
        scores = stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"pass@{k}"] = scores.mean()
        
        # strict_pass@k
        strict_scores = strict_stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"strict_pass@{k}"] = strict_scores.mean()
        
    # Error Introduction Rate (Percentage of iterations that introduced at least one new error)
    it_regression = analysis_df.groupby('iteration_id')['strict_success'].apply(lambda x: not x.all()).mean()
    row["Regression_Rate"] = it_regression
        
    results.append(row)
    results_df = pd.DataFrame(results)
    print(results_df)

    if args.save_to:
        results_df.to_csv(args.save_to, index=False)
        print(f"Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
