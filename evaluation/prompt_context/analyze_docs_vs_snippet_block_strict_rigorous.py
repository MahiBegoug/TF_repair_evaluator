import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, chi2_contingency


ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def exact_mcnemar_pvalue(docs_worse: int, docs_better: int) -> float:
    discordant = docs_worse + docs_better
    if discordant == 0:
        return 1.0
    return float(binomtest(min(docs_worse, docs_better), n=discordant, p=0.5, alternative="two-sided").pvalue)


def holm_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(n, dtype=float)
    running_max = 0.0
    for rank, idx in enumerate(order):
        raw = float(p_values[idx])
        value = min(1.0, (n - rank) * raw)
        running_max = max(running_max, value)
        adjusted[idx] = running_max
    return adjusted.tolist()


def benjamini_hochberg_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(n, dtype=float)
    running_min = 1.0
    for rev_rank, idx in enumerate(order[::-1], start=1):
        rank = n - rev_rank + 1
        raw = float(p_values[idx])
        value = min(1.0, raw * n / rank)
        running_min = min(running_min, value)
        adjusted[idx] = running_min
    return adjusted.tolist()


def bootstrap_delta_ci(
    docs_success: np.ndarray,
    snippet_success: np.ndarray,
    n_boot: int = 20000,
    seed: int = 7,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(docs_success)
    deltas = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        deltas[i] = (docs_success[idx].mean() - snippet_success[idx].mean()) * 100.0
    low, high = np.percentile(deltas, [2.5, 97.5])
    return float(low), float(high)


def build_model_table(iter1_pairs: pd.DataFrame, n_boot: int, seed: int) -> pd.DataFrame:
    rows = []
    for model, group in iter1_pairs.groupby("model", sort=False):
        docs_worse = int(group["docs_worse"].sum())
        docs_better = int(group["docs_better"].sum())
        discordant = docs_worse + docs_better
        p_value = exact_mcnemar_pvalue(docs_worse, docs_better)
        docs_rate = float(group["docs_block_strict_success"].mean())
        snippet_rate = float(group["snippet_block_strict_success"].mean())
        delta_pp = (docs_rate - snippet_rate) * 100.0
        ci_low, ci_high = bootstrap_delta_ci(
            group["docs_block_strict_success"].to_numpy(dtype=float),
            group["snippet_block_strict_success"].to_numpy(dtype=float),
            n_boot=n_boot,
            seed=seed,
        )
        odds_ratio = np.nan
        if docs_better > 0:
            odds_ratio = docs_worse / docs_better
        elif docs_worse > 0:
            odds_ratio = np.inf
        rows.append(
            {
                "model": model,
                "n_pairs": len(group),
                "docs_success_rate": docs_rate,
                "snippet_success_rate": snippet_rate,
                "delta_docs_minus_snippet_pp": delta_pp,
                "delta_ci_low_pp": ci_low,
                "delta_ci_high_pp": ci_high,
                "docs_worse_count": docs_worse,
                "docs_better_count": docs_better,
                "discordant_pairs": discordant,
                "docs_worse_share_of_discordant": (docs_worse / discordant) if discordant else np.nan,
                "discordant_odds_ratio_docs_worse_over_docs_better": odds_ratio,
                "exact_mcnemar_p_value": p_value,
            }
        )
    out = pd.DataFrame(rows)
    out["holm_p_value"] = holm_adjust(out["exact_mcnemar_p_value"].tolist())
    out["bh_fdr_p_value"] = benjamini_hochberg_adjust(out["exact_mcnemar_p_value"].tolist())
    out["significant_raw_0_05"] = out["exact_mcnemar_p_value"] < 0.05
    out["significant_holm_0_05"] = out["holm_p_value"] < 0.05
    out["significant_bh_0_05"] = out["bh_fdr_p_value"] < 0.05
    return out


def build_pooled_row(iter1_pairs: pd.DataFrame, n_boot: int, seed: int) -> pd.DataFrame:
    docs_worse = int(iter1_pairs["docs_worse"].sum())
    docs_better = int(iter1_pairs["docs_better"].sum())
    discordant = docs_worse + docs_better
    docs_rate = float(iter1_pairs["docs_block_strict_success"].mean())
    snippet_rate = float(iter1_pairs["snippet_block_strict_success"].mean())
    delta_pp = (docs_rate - snippet_rate) * 100.0
    ci_low, ci_high = bootstrap_delta_ci(
        iter1_pairs["docs_block_strict_success"].to_numpy(dtype=float),
        iter1_pairs["snippet_block_strict_success"].to_numpy(dtype=float),
        n_boot=n_boot,
        seed=seed,
    )
    row = pd.DataFrame(
        [
            {
                "scope": "all_models",
                "n_pairs": len(iter1_pairs),
                "docs_success_rate": docs_rate,
                "snippet_success_rate": snippet_rate,
                "delta_docs_minus_snippet_pp": delta_pp,
                "delta_ci_low_pp": ci_low,
                "delta_ci_high_pp": ci_high,
                "docs_worse_count": docs_worse,
                "docs_better_count": docs_better,
                "discordant_pairs": discordant,
                "docs_worse_share_of_discordant": (docs_worse / discordant) if discordant else np.nan,
                "exact_mcnemar_p_value": exact_mcnemar_pvalue(docs_worse, docs_better),
            }
        ]
    )
    return row


def build_heterogeneity_test(iter1_pairs: pd.DataFrame) -> pd.DataFrame:
    counts = (
        iter1_pairs.groupby("model", sort=False)[["docs_worse", "docs_better"]]
        .sum()
        .astype(int)
    )
    table = counts.to_numpy().T
    chi2, p_value, dof, _ = chi2_contingency(table, correction=False)
    return pd.DataFrame(
        [
            {
                "test": "chi_square_homogeneity_of_discordant_direction",
                "models_compared": len(counts),
                "chi2_stat": float(chi2),
                "dof": int(dof),
                "p_value": float(p_value),
            }
        ]
    )


def build_report(
    pooled_df: pd.DataFrame,
    model_df: pd.DataFrame,
    heterogeneity_df: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Rigorous Docs vs Snippet Iteration-1 Analysis",
            "",
            "## Primary pooled test",
            "",
            pooled_df.to_markdown(index=False),
            "",
            "## Per-model tests with multiplicity correction",
            "",
            model_df.to_markdown(index=False),
            "",
            "## Heterogeneity across models",
            "",
            heterogeneity_df.to_markdown(index=False),
            "",
            "## Interpretation",
            "",
            "- The primary claim should rely on the single pooled iteration-1 McNemar test; no multiplicity correction is needed there.",
            "- The per-model McNemar tests are secondary and should be interpreted with Holm or FDR correction.",
            "- The heterogeneity test checks whether the direction imbalance among discordant pairs differs across models, which directly supports or weakens the statement that the effect is model-dependent.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rigorous pooled and per-model iteration-1 paired analysis with multiplicity correction.")
    parser.add_argument(
        "--paired-csv",
        default="evaluation/results/tests/docs_vs_snippet_block_strict_paired/paired_docs_vs_snippet_block_strict_iteration1.csv",
        help="Paired iteration-1 docs-vs-snippet CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/tests/docs_vs_snippet_block_strict_paired/rigorous_iteration1",
        help="Directory for rigorous statistical outputs.",
    )
    parser.add_argument("--n-bootstrap", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    paired_path = resolve_path(args.paired_csv)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    iter1_pairs = pd.read_csv(paired_path)
    model_df = build_model_table(iter1_pairs, args.n_bootstrap, args.seed)
    pooled_df = build_pooled_row(iter1_pairs, args.n_bootstrap, args.seed)
    heterogeneity_df = build_heterogeneity_test(iter1_pairs)
    report = build_report(pooled_df, model_df, heterogeneity_df)

    model_path = output_dir / "per_model_mcnemar_corrected.csv"
    pooled_path = output_dir / "pooled_primary_mcnemar.csv"
    heterogeneity_path = output_dir / "discordant_direction_heterogeneity.csv"
    report_path = output_dir / "rigorous_iteration1_report.md"

    model_df.to_csv(model_path, index=False)
    pooled_df.to_csv(pooled_path, index=False)
    heterogeneity_df.to_csv(heterogeneity_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {model_path}")
    print(f"[OK] wrote {pooled_path}")
    print(f"[OK] wrote {heterogeneity_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
