import argparse
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]
SUCCESS_METRICS = ["line_success", "block_strict_success", "module_strict_success"]
SIZE_METRICS = ["prompt_tokens", "prompt_chars", "prompt_words", "prompt_lines"]


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
        return float("nan"), float("nan")
    result = spearmanr(x.astype(float), y.astype(float))
    return float(result.statistic), float(result.pvalue)


def build_correlation_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for size_metric in SIZE_METRICS:
        for success_metric in SUCCESS_METRICS:
            rho, p_value = safe_spearman(df[size_metric], df[success_metric])
            rows.append(
                {
                    "size_metric": size_metric,
                    "success_metric": success_metric,
                    "n": len(df),
                    "rho": rho,
                    "p_value": p_value,
                }
            )
    return pd.DataFrame(rows)


def build_token_quartiles(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["token_quartile"] = pd.qcut(work["prompt_tokens"], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
    summary = (
        work.groupby("token_quartile", observed=False)
        .agg(
            n=("specific_oid", "count"),
            min_prompt_tokens=("prompt_tokens", "min"),
            max_prompt_tokens=("prompt_tokens", "max"),
            mean_prompt_tokens=("prompt_tokens", "mean"),
            line_success_rate=("line_success", "mean"),
            block_strict_success_rate=("block_strict_success", "mean"),
            module_strict_success_rate=("module_strict_success", "mean"),
        )
        .reset_index()
    )
    return summary


def format_float(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.4f}"


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def build_report(
    input_csv: str,
    correlations: pd.DataFrame,
    quartiles: pd.DataFrame,
    df: pd.DataFrame,
) -> str:
    token_line = correlations[
        (correlations["size_metric"] == "prompt_tokens")
        & (correlations["success_metric"] == "line_success")
    ].iloc[0]
    token_block = correlations[
        (correlations["size_metric"] == "prompt_tokens")
        & (correlations["success_metric"] == "block_strict_success")
    ].iloc[0]
    token_module = correlations[
        (correlations["size_metric"] == "prompt_tokens")
        & (correlations["success_metric"] == "module_strict_success")
    ].iloc[0]
    strongest = (
        correlations.assign(abs_rho=lambda d: d["rho"].abs())
        .sort_values(["abs_rho", "p_value"], ascending=[False, True])
        .iloc[0]
    )

    return f"""# Prompt Token Correlation Report

## Dataset

- Input CSV: `{input_csv}`
- Rows: {len(df)}
- Mean prompt tokens: {df["prompt_tokens"].mean():.2f}
- Median prompt tokens: {df["prompt_tokens"].median():.2f}

## Spearman correlations

- `prompt_tokens` vs `line_success`: rho = {format_float(token_line["rho"])}, p = {format_float(token_line["p_value"])}
- `prompt_tokens` vs `block_strict_success`: rho = {format_float(token_block["rho"])}, p = {format_float(token_block["p_value"])}
- `prompt_tokens` vs `module_strict_success`: rho = {format_float(token_module["rho"])}, p = {format_float(token_module["p_value"])}
- Strongest absolute correlation across all size metrics: `{strongest["size_metric"]}` vs `{strongest["success_metric"]}` with rho = {format_float(strongest["rho"])}, p = {format_float(strongest["p_value"])}

## Prompt-token quartiles

{quartiles.to_markdown(index=False)}

## Interpretation

- Negative rho means larger prompts are associated with lower success.
- Positive rho means larger prompts are associated with higher success.
- Spearman here measures monotonic association, not causality.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Spearman correlation between prompt size and repair success.")
    parser.add_argument(
        "--input-csv",
        default="evaluation/results/prompt_tokens/CodeLlama_34b_Instruct_hf_docs_eval1_prompt_tokens.csv",
        help="Merged prompt-token dataset CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/prompt_tokens",
        help="Directory for correlation outputs.",
    )
    parser.add_argument(
        "--output-prefix",
        default="CodeLlama_34b_Instruct_hf_docs_eval1_prompt_tokens",
        help="Prefix for generated files.",
    )
    args = parser.parse_args()

    input_path = resolve_path(args.input_csv)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    correlations = build_correlation_table(df)
    quartiles = build_token_quartiles(df)
    report = build_report(args.input_csv, correlations, quartiles, df)

    corr_path = output_dir / f"{args.output_prefix}_spearman.csv"
    quartile_path = output_dir / f"{args.output_prefix}_quartiles.csv"
    report_path = output_dir / f"{args.output_prefix}_report.md"

    correlations.to_csv(corr_path, index=False)
    quartiles.to_csv(quartile_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {corr_path}")
    print(f"[OK] wrote {quartile_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
