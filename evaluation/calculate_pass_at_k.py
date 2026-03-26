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

    # Filter fixes to only include those for the defined problems
    # This ensures we are evaluating against the correct set of problems
    valid_oids = set(problems_df['oid'])
    fixes_df = fixes_df[fixes_df['oid'].isin(valid_oids)]

    # Using 'specific_error_fixed' as the primary success metric (Warning Removal).
    group_cols = ['oid']
    stats = fixes_df.groupby(group_cols)['specific_error_fixed'].agg(['count', 'sum']).reset_index()
    stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
    
    # Strict Pass (Regression-Free Repair): specific warning removed AND no new errors introduced
    if 'introduced_this_iteration' in fixes_df.columns:
        fixes_df['strict_success'] = fixes_df['specific_error_fixed'] & (fixes_df['introduced_this_iteration'] == 0)
        strict_stats = fixes_df.groupby(group_cols)['strict_success'].agg(['count', 'sum']).reset_index()
        strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
    else:
        strict_stats = None

    results = []

    # Determine model name from filename if possible, or use generic
    model_name = os.path.basename(args.fixes_csv).replace("_synthetic_fixes.csv", "").replace("_fixes.csv", "")

    row = {"LLM": model_name}
    for k in args.k_values:
        # Calculate standard pass@k for each problem
        scores = stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
        row[f"pass@{k}"] = scores.mean()
        
        # Calculate strict_pass@k (Regression-Free)
        if strict_stats is not None:
            strict_scores = strict_stats.apply(lambda r: pass_at_k(r['n'], r['c'], k), axis=1)
            row[f"strict_pass@{k}"] = strict_scores.mean()
            
    # Calculate Error Introduction Rate (Regression Rate)
    # What percentage of ALL attempted fixes produced by this model introduced new errors?
    if 'introduced_this_iteration' in fixes_df.columns:
        fixes_df['has_regression'] = fixes_df['introduced_this_iteration'] > 0
        row["Regression_Rate"] = fixes_df['has_regression'].mean()
        
    results.append(row)

    # Format output
    results_df = pd.DataFrame(results)
    print(results_df)

    if args.save_to:
        results_df.to_csv(args.save_to, index=False)
        print(f"Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
