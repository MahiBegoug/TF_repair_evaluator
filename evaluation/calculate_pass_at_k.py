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

    # Calculate n and c per problem (oid)
    # We assume the input fixes CSV corresponds to a single model
    # Using 'line_is_clean' as the primary success metric (True if line has no errors after fix)
    # Alternative: 'specific_error_fixed' tracks if the exact error type was resolved
    group_cols = ['oid']
    stats = fixes_df.groupby(group_cols)['line_is_clean'].agg(['count', 'sum']).reset_index()
    stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)

    results = []

    # Determine model name from filename if possible, or use generic
    model_name = os.path.basename(args.fixes_csv).replace("_synthetic_fixes.csv", "").replace("_fixes.csv", "")

    row = {"LLM": model_name}
    for k in args.k_values:
        # Calculate pass@k for each problem
        scores = stats.apply(lambda row: pass_at_k(row['n'], row['c'], k), axis=1)
        avg_score = scores.mean()
        row[f"pass@{k}"] = avg_score
    results.append(row)

    # Format output
    results_df = pd.DataFrame(results)
    print(results_df)

    if args.save_to:
        results_df.to_csv(args.save_to, index=False)
        print(f"Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
