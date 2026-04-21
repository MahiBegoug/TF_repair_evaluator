import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon


def rank_biserial(x: np.ndarray, y: np.ndarray) -> float:
    diffs = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    non_zero = diffs[diffs != 0]
    if len(non_zero) == 0:
        return 0.0
    ranks = rankdata(np.abs(non_zero), method="average")
    pos_sum = float(ranks[non_zero > 0].sum())
    neg_sum = float(ranks[non_zero < 0].sum())
    total = pos_sum + neg_sum
    if total == 0:
        return 0.0
    return (pos_sum - neg_sum) / total


def rank_biserial_magnitude(effect: float) -> str:
    a = abs(effect)
    if a < 0.10:
        return "negligible"
    if a < 0.30:
        return "small"
    if a < 0.50:
        return "medium"
    return "large"


def load_per_instance(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["specific_oid"].astype(str) != "MEAN"].copy()
    df["specific_oid"] = df["specific_oid"].astype(str)
    return df


def split_variant(model_name: str) -> tuple[str, str] | None:
    docs_suffix = "_docs_snippet_marked_code_only_xml"
    snippet_suffix = "_snippet_marked_code_only_xml"
    if model_name.endswith(docs_suffix):
        return model_name[: -len(docs_suffix)], "docs"
    if model_name.endswith(snippet_suffix):
        return model_name[: -len(snippet_suffix)], "snippet"
    return None


def run_family(results_dir: Path, suffix: str) -> pd.DataFrame:
    files = sorted(results_dir.glob(f"*_{suffix}_pass_at_k_1_to_11.csv"))
    loaded = {path.stem.replace(f"_{suffix}_pass_at_k_1_to_11", ""): load_per_instance(path) for path in files}
    grouped: dict[str, dict[str, pd.DataFrame]] = {}
    for model_name, df in loaded.items():
        parts = split_variant(model_name)
        if parts is None:
            continue
        base_name, variant = parts
        grouped.setdefault(base_name, {})[variant] = df

    rows = []
    for base_name, variants in sorted(grouped.items()):
        if "docs" not in variants or "snippet" not in variants:
            continue
        model_a = f"{base_name}_docs_snippet_marked_code_only_xml"
        model_b = f"{base_name}_snippet_marked_code_only_xml"
        a = variants["docs"]
        b = variants["snippet"]
        merged = a.merge(b, on="specific_oid", suffixes=("_a", "_b"))
        for k in range(1, 12):
            col_a = f"pass@{k}_a"
            col_b = f"pass@{k}_b"
            xa = merged[col_a].to_numpy(dtype=float)
            xb = merged[col_b].to_numpy(dtype=float)
            if np.allclose(xa, xb):
                stat = 0.0
                p_value = 1.0
            else:
                res = wilcoxon(xa, xb, zero_method="wilcox", alternative="two-sided", method="auto")
                stat = float(res.statistic)
                p_value = float(res.pvalue)
            effect = rank_biserial(xa, xb)
            rows.append(
                {
                    "metric_family": suffix,
                    "model_a": model_a,
                    "model_b": model_b,
                    "k": k,
                    "mean_a": xa.mean(),
                    "mean_b": xb.mean(),
                    "delta_a_minus_b": xa.mean() - xb.mean(),
                    "wilcoxon_stat": stat,
                    "wilcoxon_p_value": p_value,
                    "rank_biserial": effect,
                    "rank_biserial_magnitude": rank_biserial_magnitude(effect),
                    "n_instances": len(merged),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pairwise Wilcoxon + rank-biserial for strict pass@k files")
    parser.add_argument("--results-dir", default="evaluation/results")
    parser.add_argument("--output-dir", default="evaluation/results/statistical_test")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results_dir = root / args.results_dir
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    block = run_family(results_dir, "block_strict")
    module = run_family(results_dir, "module_strict")

    block_csv = output_dir / "pairwise_block_strict_wilcoxon_rank_biserial.csv"
    module_csv = output_dir / "pairwise_module_strict_wilcoxon_rank_biserial.csv"

    block.to_csv(block_csv, index=False)
    module.to_csv(module_csv, index=False)

    print(f"[OK] wrote {block_csv}")
    print(f"[OK] wrote {module_csv}")


if __name__ == "__main__":
    main()
