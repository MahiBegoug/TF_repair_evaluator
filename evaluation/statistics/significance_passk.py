import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.passk.calculate_corrected import pass_at_k

MODEL_FILES = {
    "CodeLlama_34b_Instruct_hf": {
        "docs": "llms_fixes_results/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet": "llms_fixes_results/CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml_repair_results.csv",
    },
    "Codestral_22B_v0.1": {
        "docs": "llms_fixes_results/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet": "llms_fixes_results/Codestral_22B_v0.1_snippet_marked_code_only_xml_repair_results.csv",
    },
    "deepseek_coder_33b_instruct": {
        "docs": "llms_fixes_results/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet": "llms_fixes_results/deepseek_coder_33b_instruct_snippet_marked_code_only_xml_repair_results.csv",
    },
    "gpt_oss_20b": {
        "docs": "llms_fixes_results/gpt_oss_20b_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet": "llms_fixes_results/gpt_oss_20b_snippet_marked_code_only_xml_repair_results.csv",
    },
}

METRIC_DEFS = {
    "pass": lambda df: df["line_specific_error_fixed"].fillna(False).astype(bool),
    "block_strict": lambda df: (
        df["line_specific_error_fixed"].fillna(False).astype(bool)
        & (df["block_fix_introduced_errors"].fillna(0).astype(int) == 0)
    ),
}


def per_problem_scores(df: pd.DataFrame, valid_keys: list[str], metric: str, k_values: list[int]) -> pd.DataFrame:
    df = df.copy()
    df["specific_oid"] = df["specific_oid"].astype(str)
    df["success"] = METRIC_DEFS[metric](df)
    grouped = df.groupby("specific_oid")["success"].agg(["count", "sum"]).reset_index()
    grouped = pd.DataFrame({"specific_oid": valid_keys}).merge(grouped, on="specific_oid", how="left").fillna({"count": 0, "sum": 0})
    grouped["count"] = grouped["count"].astype(int)
    grouped["sum"] = grouped["sum"].astype(int)

    out = pd.DataFrame({"specific_oid": grouped["specific_oid"]})
    for k in k_values:
        out[f"k{k}"] = grouped.apply(lambda r: pass_at_k(int(r["count"]), int(r["sum"]), k), axis=1)
    return out


def paired_bootstrap_pvalue(a: np.ndarray, b: np.ndarray, rng: np.random.Generator, n_boot: int) -> tuple[float, float, float, float]:
    diff = a - b
    observed = float(diff.mean())
    n = len(diff)
    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_means[i] = diff[idx].mean()
    ci_low, ci_high = np.percentile(boot_means, [2.5, 97.5])

    centered = diff - observed
    null_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        null_means[i] = centered[idx].mean()
    p_two_sided = float((np.abs(null_means) >= abs(observed)).mean())
    return observed, float(ci_low), float(ci_high), p_two_sided


def wilcoxon_signed_rank_with_effect(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    diff = a - b
    nonzero = diff[diff != 0]
    if len(nonzero) == 0:
        return 0.0, 1.0, 0.0

    res = wilcoxon(diff, zero_method="wilcox", alternative="two-sided", method="auto")

    abs_diff = np.abs(nonzero)
    ranks = rankdata(abs_diff, method="average")
    w_plus = float(ranks[nonzero > 0].sum())
    w_minus = float(ranks[nonzero < 0].sum())
    rank_biserial = 0.0
    total = w_plus + w_minus
    if total > 0:
        rank_biserial = (w_plus - w_minus) / total

    return float(res.statistic), float(res.pvalue), float(rank_biserial)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired bootstrap significance test for pass@k variants")
    parser.add_argument("--problems-csv", default="problems/benchmark_template_dedup_deterministic.csv")
    parser.add_argument("--metric", choices=sorted(METRIC_DEFS), nargs="+", default=["pass", "block_strict"])
    parser.add_argument("--k-values", nargs="+", type=int, default=[1, 5, 10])
    parser.add_argument("--n-bootstrap", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--save-csv", default="evaluation/results/docs_vs_snippet_significance.csv")
    parser.add_argument("--save-md", default="evaluation/results/docs_vs_snippet_significance.md")
    args = parser.parse_args()

    problems = pd.read_csv(ROOT / args.problems_csv)
    valid_keys = sorted(problems["specific_oid"].astype(str).unique().tolist())

    rng = np.random.default_rng(args.seed)
    rows = []
    for model, files in MODEL_FILES.items():
        docs_df = pd.read_csv(ROOT / files["docs"])
        snippet_df = pd.read_csv(ROOT / files["snippet"])
        for metric in args.metric:
            docs_scores = per_problem_scores(docs_df, valid_keys, metric, args.k_values)
            snippet_scores = per_problem_scores(snippet_df, valid_keys, metric, args.k_values)
            merged = docs_scores.merge(snippet_scores, on="specific_oid", suffixes=("_docs", "_snippet"))
            for k in args.k_values:
                a = merged[f"k{k}_docs"].to_numpy(dtype=float)
                b = merged[f"k{k}_snippet"].to_numpy(dtype=float)
                observed, ci_low, ci_high, pval = paired_bootstrap_pvalue(a, b, rng, args.n_bootstrap)
                w_stat, w_pval, rank_biserial = wilcoxon_signed_rank_with_effect(a, b)
                rows.append(
                    {
                        "model": model,
                        "metric": metric,
                        "k": k,
                        "docs_mean": a.mean(),
                        "snippet_mean": b.mean(),
                        "delta_docs_minus_snippet": observed,
                        "ci_low": ci_low,
                        "ci_high": ci_high,
                        "bootstrap_p_value": pval,
                        "wilcoxon_stat": w_stat,
                        "wilcoxon_p_value": w_pval,
                        "wilcoxon_rank_biserial": rank_biserial,
                        "significant_0_05": w_pval < 0.05,
                    }
                )

    results = pd.DataFrame(rows)
    csv_path = ROOT / args.save_csv
    md_path = ROOT / args.save_md
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(csv_path, index=False)

    md = results.copy()
    for col in ["docs_mean", "snippet_mean", "delta_docs_minus_snippet", "ci_low", "ci_high"]:
        md[col] = md[col].map(lambda x: f"{x*100:.2f}%")
    md["bootstrap_p_value"] = md["bootstrap_p_value"].map(lambda x: f"{x:.4f}")
    md["wilcoxon_stat"] = md["wilcoxon_stat"].map(lambda x: f"{x:.1f}")
    md["wilcoxon_p_value"] = md["wilcoxon_p_value"].map(lambda x: f"{x:.4f}")
    md["wilcoxon_rank_biserial"] = md["wilcoxon_rank_biserial"].map(lambda x: f"{x:.3f}")
    md["significant_0_05"] = md["significant_0_05"].map(lambda x: "yes" if x else "no")
    md_path.write_text(md.to_markdown(index=False), encoding="utf-8")

    print(results.to_string(index=False))
    print(f"\nSaved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
