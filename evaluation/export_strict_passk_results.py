import argparse
from pathlib import Path

import pandas as pd


def pass_at_k(n: int, c: int, k: int) -> float:
    if n <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    prob_all_fail = 1.0
    for i in range(k):
        prob_all_fail *= (n - c - i) / (n - i)
    return 1.0 - prob_all_fail


def compute_metric_scores(df: pd.DataFrame, benchmark_ids: list[str], success_col: str, k_values: list[int]) -> pd.DataFrame:
    stats = (
        df.groupby("specific_oid")[success_col]
        .agg(["count", "sum"])
        .reset_index()
    )
    stats = (
        pd.DataFrame({"specific_oid": benchmark_ids})
        .merge(stats, on="specific_oid", how="left")
        .fillna({"count": 0, "sum": 0})
    )
    stats["count"] = stats["count"].astype(int)
    stats["sum"] = stats["sum"].astype(int)

    ordered = df[["specific_oid", "iteration_id", success_col]].copy()
    ordered = ordered.sort_values(["specific_oid", "iteration_id"])

    result = stats[["specific_oid"]].copy()
    result["n_attempts"] = stats["count"]
    result["c_successes"] = stats["sum"]
    result["fixed_any"] = (stats["sum"] > 0).astype(int)

    for k in k_values:
        result[f"pass@{k}"] = stats.apply(lambda r: pass_at_k(int(r["count"]), int(r["sum"]), int(k)), axis=1)

        fixed_at_k = (
            ordered.groupby("specific_oid")[success_col]
            .apply(lambda s, kk=k: int(bool(s.head(kk).any())))
            .reset_index(name=f"fixed_at_{k}")
        )
        result = result.merge(fixed_at_k, on="specific_oid", how="left")
        result[f"fixed_at_{k}"] = result[f"fixed_at_{k}"].fillna(0).astype(int)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export block-strict and module-strict pass@k files per model")
    parser.add_argument("--problems-csv", default="problems/benchmark_template_dedup_deterministic.csv")
    parser.add_argument("--repairs-dir", default="llms_fixes_results")
    parser.add_argument("--results-dir", default="evaluation/results")
    parser.add_argument("--k-max", type=int, default=11)
    parser.add_argument("--clear-results-files", action="store_true", help="Delete top-level files in results-dir before exporting")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    problems_csv = root / args.problems_csv
    repairs_dir = root / args.repairs_dir
    results_dir = root / args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    if args.clear_results_files:
        for path in results_dir.iterdir():
            if path.is_file():
                path.unlink()
                print(f"[CLEAR] removed {path}")

    problems = pd.read_csv(problems_csv)
    problems["specific_oid"] = problems["specific_oid"].astype(str).str.strip()
    benchmark_ids = sorted(problems["specific_oid"].unique().tolist())
    benchmark_meta = (
        problems[["specific_oid", "project_name", "filename", "summary"]]
        .drop_duplicates(subset=["specific_oid"])
        .sort_values("specific_oid")
    )
    k_values = list(range(1, args.k_max + 1))

    repair_files = sorted(repairs_dir.glob("*_repair_results.csv"))
    for repair_file in repair_files:
        df = pd.read_csv(repair_file)
        df["specific_oid"] = df["specific_oid"].astype(str).str.strip()
        df["line_specific_error_fixed"] = df["line_specific_error_fixed"].fillna(False).astype(bool)
        df["block_fix_introduced_errors"] = df["block_fix_introduced_errors"].fillna(0).astype(int)
        df["module_fix_introduced_errors"] = df["module_fix_introduced_errors"].fillna(0).astype(int)

        # Enforce one row per (specific_oid, iteration_id)
        df = df.drop_duplicates(subset=["specific_oid", "iteration_id"], keep="first")

        df["block_strict_success"] = df["line_specific_error_fixed"] & (df["block_fix_introduced_errors"] == 0)
        df["module_strict_success"] = df["line_specific_error_fixed"] & (df["module_fix_introduced_errors"] == 0)

        model_name = repair_file.name.replace("_repair_results.csv", "")

        block_scores = compute_metric_scores(df, benchmark_ids, "block_strict_success", k_values)
        module_scores = compute_metric_scores(df, benchmark_ids, "module_strict_success", k_values)

        block_row = benchmark_meta.merge(block_scores, on="specific_oid", how="left")
        module_row = benchmark_meta.merge(module_scores, on="specific_oid", how="left")

        block_mean = {
            "specific_oid": "MEAN",
            "project_name": "",
            "filename": "",
            "summary": "",
        }
        module_mean = {
            "specific_oid": "MEAN",
            "project_name": "",
            "filename": "",
            "summary": "",
        }
        block_mean["n_attempts"] = block_row["n_attempts"].mean()
        block_mean["c_successes"] = block_row["c_successes"].mean()
        block_mean["fixed_any"] = block_row["fixed_any"].mean()
        module_mean["n_attempts"] = module_row["n_attempts"].mean()
        module_mean["c_successes"] = module_row["c_successes"].mean()
        module_mean["fixed_any"] = module_row["fixed_any"].mean()

        for k in k_values:
            col = f"pass@{k}"
            block_mean[col] = block_row[col].mean()
            module_mean[col] = module_row[col].mean()
            fixed_col = f"fixed_at_{k}"
            block_mean[fixed_col] = block_row[fixed_col].mean()
            module_mean[fixed_col] = module_row[fixed_col].mean()
        block_row = pd.concat([block_row, pd.DataFrame([block_mean])], ignore_index=True)
        module_row = pd.concat([module_row, pd.DataFrame([module_mean])], ignore_index=True)

        block_path = results_dir / f"{model_name}_block_strict_pass_at_k_1_to_{args.k_max}.csv"
        module_path = results_dir / f"{model_name}_module_strict_pass_at_k_1_to_{args.k_max}.csv"
        block_row.to_csv(block_path, index=False)
        module_row.to_csv(module_path, index=False)
        print(f"[OK] wrote {block_path.name}")
        print(f"[OK] wrote {module_path.name}")


if __name__ == "__main__":
    main()
