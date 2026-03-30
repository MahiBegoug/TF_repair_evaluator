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
    parser = argparse.ArgumentParser(description="Calculate pass@k with ground-truth verification and methodological safeguards")
    parser.add_argument("--problems-csv", required=True, help="Path to problems CSV")
    parser.add_argument("--fixes-csv", required=True, help="Path to fixes/outcomes CSV")
    parser.add_argument("--k-values", nargs="+", type=int, default=[1, 5, 10], help="Values of k")
    parser.add_argument("--save-to", help="Path to save results")
    args = parser.parse_args()

    try:
        problems_df = pd.read_csv(args.problems_csv)
        fixes_df = pd.read_csv(args.fixes_csv)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # SCHEMA VALIDATION: Define the required outcome columns
    OUTCOME_COLUMNS = [
        'oid', 'iteration_id', 'llm_name', 'filename', 
        'line_specific_error_fixed', 'module_fix_introduced_errors', 'block_fix_introduced_errors'
    ]
    # Check if this is an Outcome CSV by looking for the primary success flag
    is_outcome_csv = 'line_specific_error_fixed' in fixes_df.columns

    # Choose which column to treat as the evaluation OID for this run.
    # - When evaluating against problems/problems.csv, prefer `benchmark_oid` (if it matches).
    # - When evaluating against ALL_LABELED (location OIDs), prefer `oid` (location) even if
    #   `benchmark_oid` exists in the file.
    def _choose_eval_oid_col(df: pd.DataFrame, valid: set[str]) -> str:
        best_col = None
        best_rate = -1.0
        for col in ("benchmark_oid", "oid"):
            if col not in df.columns:
                continue
            s = df[col].fillna("").astype(str).str.strip()
            nonempty = s != ""
            if nonempty.any():
                rate = float(s[nonempty].isin(valid).mean())
            else:
                rate = 0.0
            if rate > best_rate:
                best_rate = rate
                best_col = col
        return best_col or "oid"

    # SAFEGUARD: Filter to valid benchmark OIDs (only safe for Outcome CSVs).
    # Diagnostics CSVs often use a different `oid` scheme (e.g., location-based)
    # and should be mapped via `specific_oid` or `original_problem_oid` instead.
    valid_oids = set(problems_df['oid'].astype(str))
    eval_oid_col = _choose_eval_oid_col(fixes_df, valid_oids) if is_outcome_csv else "oid"
    if is_outcome_csv:
        print(f"Using evaluation OID column: {eval_oid_col}")
    if is_outcome_csv and eval_oid_col in fixes_df.columns:
        original_count = len(fixes_df)
        fixes_df[eval_oid_col] = fixes_df[eval_oid_col].astype(str)
        fixes_df = fixes_df[fixes_df[eval_oid_col].isin(valid_oids)]
        filtered_count = len(fixes_df)
        if filtered_count < original_count:
            print(f"SAFEGUARD: Filtered out {original_count - filtered_count} rows with OIDs not present in the problems benchmark.")

    # HARDENING Improvement A: Enforce one row = one candidate attempt (Outcome CSV only).
    # Diagnostics CSVs can legitimately contain multiple rows per iteration (many diagnostics per module),
    # so deduplicating by (oid, iteration_id) would delete real signals.
    if is_outcome_csv and eval_oid_col in fixes_df.columns and 'iteration_id' in fixes_df.columns:
        dups = fixes_df.duplicated(subset=[eval_oid_col, 'iteration_id'], keep=False)
        if dups.any():
            print(f"WARNING: {dups.sum()} duplicate ({eval_oid_col}, iteration_id) rows detected. Keeping only the first occurrence.")
            fixes_df = fixes_df.drop_duplicates(subset=[eval_oid_col, 'iteration_id'], keep='first')

    if is_outcome_csv:
        print("Detected Outcome CSV (Ground Truth). Validating schema and applying coercion.")
        
        # Verify presence of requested outcome columns (warn if missing)
        missing_cols = [c for c in OUTCOME_COLUMNS if c not in fixes_df.columns]
        if missing_cols:
            print(f"NOTE: Outcomes CSV is missing some detail columns: {missing_cols}. Using available survivors.")

        # HARDENING Improvement B: Handle booleans and NaNs safely
        fixes_df['line_specific_error_fixed'] = fixes_df['line_specific_error_fixed'].fillna(False).astype(bool)
        
        # SCOPE-SEPARATED METRICS (Improvement E)
        # 1. Block-Level
        if 'block_fix_introduced_errors' in fixes_df.columns:
            fixes_df['block_fix_introduced_errors'] = fixes_df['block_fix_introduced_errors'].fillna(0).astype(int)
            fixes_df['block_strict_success'] = (fixes_df['line_specific_error_fixed'] == True) & (fixes_df['block_fix_introduced_errors'] == 0)
        else:
            fixes_df['block_strict_success'] = fixes_df['line_specific_error_fixed'] # Fallback
            
        # 2. Module-Level
        if 'module_fix_introduced_errors' in fixes_df.columns:
            fixes_df['module_fix_introduced_errors'] = fixes_df['module_fix_introduced_errors'].fillna(0).astype(int)
            fixes_df['module_strict_success'] = (fixes_df['line_specific_error_fixed'] == True) & (fixes_df['module_fix_introduced_errors'] == 0)
        else:
            fixes_df['module_strict_success'] = fixes_df['block_strict_success'] # Fallback
            
        # Regression Rates
        block_reg_rate = (fixes_df['block_fix_introduced_errors'] > 0).mean() if 'block_fix_introduced_errors' in fixes_df.columns else 0.0
        module_reg_rate = (fixes_df['module_fix_introduced_errors'] > 0).mean() if 'module_fix_introduced_errors' in fixes_df.columns else 0.0
        
        # Group by benchmark OID to get n and c
        stats = fixes_df.groupby(eval_oid_col)['line_specific_error_fixed'].agg(['count', 'sum']).reset_index()
        stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
        
        block_strict_stats = fixes_df.groupby(eval_oid_col)['block_strict_success'].agg(['count', 'sum']).reset_index()
        block_strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
        
        module_strict_stats = fixes_df.groupby(eval_oid_col)['module_strict_success'].agg(['count', 'sum']).reset_index()
        module_strict_stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
        
    else:
        print("Detected Diagnostics CSV (Raw Diagnostics). WARNING: Fallback logic (Absence-based inference).")
        # IMPORTANT: Diagnostics CSV uses different columns (e.g., is_original_error)
        fixes_df['iteration_id'] = fixes_df['iteration_id'].fillna(0).astype(int)
        all_oids = list(valid_oids)
        num_iterations = fixes_df['iteration_id'].max() if not fixes_df.empty else 0
        
        existing_diagnostic_set = set()
        # Prefer mapping via specific_oid -> benchmark oid when possible.
        # This is necessary because diagnostics `oid` and `original_problem_oid` may be location-based
        # and not equal to the benchmark problems `oid`.
        problems_spec_to_oid = {}
        if 'specific_oid' in problems_df.columns:
            problems_spec_to_oid = dict(
                zip(
                    problems_df['specific_oid'].fillna("").astype(str),
                    problems_df['oid'].fillna("").astype(str),
                )
            )

        if 'is_original_error' in fixes_df.columns:
            original_mask = fixes_df['is_original_error'].fillna(False).astype(bool)
            orig_df = fixes_df[original_mask].copy()

            mapped_ok = 0
            mapped_total = 0

            for _, row in orig_df.iterrows():
                it = int(row.get('iteration_id', 0))

                mapped_oid = None
                spec = str(row.get('specific_oid', '') or '').strip()
                if spec and spec in problems_spec_to_oid:
                    mapped_oid = problems_spec_to_oid.get(spec)

                # Fallback: if original_problem_oid already happens to be a benchmark oid, accept it.
                if not mapped_oid:
                    op = str(row.get('original_problem_oid', '') or '').strip()
                    if op and op in valid_oids:
                        mapped_oid = op

                mapped_total += 1
                if mapped_oid and mapped_oid in valid_oids:
                    mapped_ok += 1
                    existing_diagnostic_set.add((mapped_oid, it))

            if mapped_total > 0 and mapped_ok < mapped_total:
                print(
                    f"NOTE: Mapped {mapped_ok}/{mapped_total} original-error diagnostic rows to benchmark OIDs. "
                    f"Unmapped rows are ignored for pass@k (likely non-benchmark diagnostics)."
                )
        else:
            print("Error: Diagnostics CSV is missing 'is_original_error'. Cannot perform fallback evaluation.")
            return

        rows = []
        for oid in all_oids:
            for it in range(1, int(num_iterations) + 1):
                is_fixed = (oid, it) not in existing_diagnostic_set
                rows.append({'oid': oid, 'is_fixed': is_fixed})
        
        if not rows:
             print("Error: No valid attempt rows found for evaluation.")
             return

        analysis_df = pd.DataFrame(rows)
        stats = analysis_df.groupby('oid')['is_fixed'].agg(['count', 'sum']).reset_index()
        stats.rename(columns={'count': 'n', 'sum': 'c'}, inplace=True)
        block_strict_stats = stats
        module_strict_stats = stats
        block_reg_rate = 0.0
        module_reg_rate = 0.0

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
    
    print("\n--- FINAL EVALUATION RESULTS ---")
    print(results_df.to_string(index=False))

    if args.save_to:
        os.makedirs(os.path.dirname(args.save_to), exist_ok=True)
        results_df.to_csv(args.save_to, index=False)
        print(f"Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
