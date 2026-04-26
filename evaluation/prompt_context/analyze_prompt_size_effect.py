import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]

MODEL_FILES = {
    "CodeLlama_34b_Instruct_hf": {
        "docs": "CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml",
        "snippet": "CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml",
    },
    "Codestral_22B_v0.1": {
        "docs": "Codestral_22B_v0.1_docs_snippet_marked_code_only_xml",
        "snippet": "Codestral_22B_v0.1_snippet_marked_code_only_xml",
    },
    "deepseek_coder_33b_instruct": {
        "docs": "deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml",
        "snippet": "deepseek_coder_33b_instruct_snippet_marked_code_only_xml",
    },
    "gpt_oss_20b": {
        "docs": "gpt_oss_20b_docs_snippet_marked_code_only_xml",
        "snippet": "gpt_oss_20b_snippet_marked_code_only_xml",
    },
}

SIZE_METRICS = ["prompt_chars", "prompt_words", "prompt_lines"]
SUCCESS_METRICS = ["line_success", "block_strict_success", "module_strict_success"]


def _safe_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def load_iteration_records(iteration_id: int) -> pd.DataFrame:
    frames = []

    for model, variants in MODEL_FILES.items():
        for variant, base_name in variants.items():
            prompt_path = ROOT / "llm_responses" / f"{base_name}.csv"
            results_path = ROOT / "llms_fixes_results" / f"{base_name}_repair_results.csv"

            prompt_df = pd.read_csv(prompt_path)
            results_df = pd.read_csv(results_path)

            prompt_df["specific_oid"] = prompt_df["specific_oid"].astype(str)
            prompt_df["iteration_id"] = prompt_df["iteration_id"].astype(int)
            results_df["specific_oid"] = results_df["specific_oid"].astype(str)
            results_df["iteration_id"] = results_df["iteration_id"].astype(int)

            merged = prompt_df.merge(
                results_df,
                on=["specific_oid", "iteration_id"],
                how="inner",
                suffixes=("_prompt", "_result"),
            )
            merged = merged[merged["iteration_id"] == iteration_id].copy()
            if merged.empty:
                continue

            for column in ["project_name", "filename", "summary", "detail", "severity"]:
                prompt_name = f"{column}_prompt"
                result_name = f"{column}_result"
                if column not in merged.columns:
                    if prompt_name in merged.columns:
                        merged[column] = merged[prompt_name]
                    elif result_name in merged.columns:
                        merged[column] = merged[result_name]
                    else:
                        merged[column] = ""

            prompt_text = _safe_text(merged["prompt_content"])
            merged["model"] = model
            merged["variant"] = variant
            merged["prompt_chars"] = prompt_text.str.len()
            merged["prompt_words"] = prompt_text.str.split().str.len()
            merged["prompt_lines"] = prompt_text.str.count("\n") + 1
            merged["line_success"] = merged["line_specific_error_fixed"].fillna(False).astype(bool).astype(int)
            merged["block_strict_success"] = (
                merged["line_specific_error_fixed"].fillna(False).astype(bool)
                & (merged["block_fix_introduced_errors"].fillna(0).astype(int) == 0)
            ).astype(int)
            merged["module_strict_success"] = (
                merged["line_specific_error_fixed"].fillna(False).astype(bool)
                & (merged["module_fix_introduced_errors"].fillna(0).astype(int) == 0)
            ).astype(int)
            merged["prompt_style"] = np.where(
                merged["variant"] == "docs",
                "Local Context + Schema",
                "Local Context",
            )

            keep = [
                "model",
                "variant",
                "prompt_style",
                "specific_oid",
                "iteration_id",
                "project_name",
                "filename",
                "summary",
                "detail",
                "severity",
                "prompt_content",
                "prompt_chars",
                "prompt_words",
                "prompt_lines",
                "line_success",
                "block_strict_success",
                "module_strict_success",
                "is_fixed",
                "block_fix_introduced_errors",
                "module_fix_introduced_errors",
            ]
            frames.append(merged[keep])

    if not frames:
        raise ValueError(f"No iteration-{iteration_id} prompt/result matches were found.")

    return pd.concat(frames, ignore_index=True)


def summarize_iteration_records(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, group in df.groupby("variant", sort=False):
        rows.append(
            {
                "scope": "variant",
                "scope_value": variant,
                "n": len(group),
                "line_success_rate": group["line_success"].mean(),
                "block_strict_success_rate": group["block_strict_success"].mean(),
                "module_strict_success_rate": group["module_strict_success"].mean(),
                "prompt_chars_mean": group["prompt_chars"].mean(),
                "prompt_chars_median": group["prompt_chars"].median(),
                "prompt_words_mean": group["prompt_words"].mean(),
                "prompt_words_median": group["prompt_words"].median(),
                "prompt_lines_mean": group["prompt_lines"].mean(),
                "prompt_lines_median": group["prompt_lines"].median(),
            }
        )

    rows.append(
        {
            "scope": "all",
            "scope_value": "all",
            "n": len(df),
            "line_success_rate": df["line_success"].mean(),
            "block_strict_success_rate": df["block_strict_success"].mean(),
            "module_strict_success_rate": df["module_strict_success"].mean(),
            "prompt_chars_mean": df["prompt_chars"].mean(),
            "prompt_chars_median": df["prompt_chars"].median(),
            "prompt_words_mean": df["prompt_words"].mean(),
            "prompt_words_median": df["prompt_words"].median(),
            "prompt_lines_mean": df["prompt_lines"].mean(),
            "prompt_lines_median": df["prompt_lines"].median(),
        }
    )

    return pd.DataFrame(rows)


def safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    x = pd.Series(x).astype(float)
    y = pd.Series(y).astype(float)
    if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
        return np.nan, np.nan
    result = spearmanr(x, y)
    return float(result.statistic), float(result.pvalue)


def build_spearman_summary(df: pd.DataFrame) -> pd.DataFrame:
    scopes = [("all", "all", df)]
    scopes.extend((("variant", variant, group) for variant, group in df.groupby("variant", sort=False)))
    scopes.extend((("model", model, group) for model, group in df.groupby("model", sort=False)))
    scopes.extend(
        (
            ("model_variant", f"{model}::{variant}", group)
            for (model, variant), group in df.groupby(["model", "variant"], sort=False)
        )
    )

    rows = []
    for scope_name, scope_value, group in scopes:
        for size_metric in SIZE_METRICS:
            for success_metric in SUCCESS_METRICS:
                rho, p_value = safe_spearman(group[size_metric], group[success_metric])
                rows.append(
                    {
                        "analysis": "raw_prompt_size_vs_success",
                        "scope": scope_name,
                        "scope_value": scope_value,
                        "size_metric": size_metric,
                        "success_metric": success_metric,
                        "n": len(group),
                        "rho": rho,
                        "p_value": p_value,
                    }
                )
    return pd.DataFrame(rows)


def build_paired_records(df: pd.DataFrame) -> pd.DataFrame:
    docs = df[df["variant"] == "docs"].copy()
    snippet = df[df["variant"] == "snippet"].copy()

    pair_keys = ["model", "specific_oid", "iteration_id"]
    pairs = docs.merge(snippet, on=pair_keys, suffixes=("_docs", "_snippet"), how="inner")
    if pairs.empty:
        raise ValueError("No matched docs/snippet pairs were found for the requested iteration.")

    for size_metric in SIZE_METRICS:
        pairs[f"delta_{size_metric}"] = pairs[f"{size_metric}_docs"] - pairs[f"{size_metric}_snippet"]

    for success_metric in SUCCESS_METRICS:
        pairs[f"delta_{success_metric}"] = pairs[f"{success_metric}_docs"] - pairs[f"{success_metric}_snippet"]

    pairs["line_outcome"] = np.select(
        [
            pairs["delta_line_success"] < 0,
            pairs["delta_line_success"] > 0,
        ],
        [
            "docs_worse",
            "docs_better",
        ],
        default="tie",
    )
    pairs["block_outcome"] = np.select(
        [
            pairs["delta_block_strict_success"] < 0,
            pairs["delta_block_strict_success"] > 0,
        ],
        [
            "docs_worse",
            "docs_better",
        ],
        default="tie",
    )
    pairs["prompt_char_ratio"] = pairs["prompt_chars_docs"] / pairs["prompt_chars_snippet"].replace(0, np.nan)
    return pairs


def build_pair_delta_spearman(pairs: pd.DataFrame) -> pd.DataFrame:
    scopes = [("all", "all", pairs)]
    scopes.extend((("model", model, group) for model, group in pairs.groupby("model", sort=False)))

    rows = []
    for scope_name, scope_value, group in scopes:
        for size_metric in SIZE_METRICS:
            delta_size = f"delta_{size_metric}"
            for success_metric in SUCCESS_METRICS:
                delta_success = f"delta_{success_metric}"
                rho, p_value = safe_spearman(group[delta_size], group[delta_success])
                rows.append(
                    {
                        "analysis": "paired_prompt_delta_vs_success_delta",
                        "scope": scope_name,
                        "scope_value": scope_value,
                        "size_metric": delta_size,
                        "success_metric": delta_success,
                        "n": len(group),
                        "rho": rho,
                        "p_value": p_value,
                    }
                )
    return pd.DataFrame(rows)


def build_interesting_cases(pairs: pd.DataFrame, top_n: int) -> pd.DataFrame:
    columns = [
        "model",
        "specific_oid",
        "project_name_docs",
        "filename_docs",
        "summary_docs",
        "detail_docs",
        "prompt_chars_docs",
        "prompt_chars_snippet",
        "delta_prompt_chars",
        "prompt_words_docs",
        "prompt_words_snippet",
        "delta_prompt_words",
        "prompt_lines_docs",
        "prompt_lines_snippet",
        "delta_prompt_lines",
        "line_success_docs",
        "line_success_snippet",
        "delta_line_success",
        "block_strict_success_docs",
        "block_strict_success_snippet",
        "delta_block_strict_success",
        "module_strict_success_docs",
        "module_strict_success_snippet",
        "delta_module_strict_success",
        "line_outcome",
        "block_outcome",
    ]

    docs_worse = (
        pairs[pairs["line_outcome"] == "docs_worse"]
        .sort_values(["delta_prompt_chars", "delta_prompt_words"], ascending=False)
        .head(top_n)
    )
    docs_better = (
        pairs[pairs["line_outcome"] == "docs_better"]
        .sort_values(["delta_prompt_chars", "delta_prompt_words"], ascending=False)
        .head(top_n)
    )
    ties = (
        pairs[pairs["line_outcome"] == "tie"]
        .sort_values(["delta_prompt_chars", "prompt_chars_docs"], ascending=False)
        .head(top_n)
    )

    selected = pd.concat(
        [
            docs_worse.assign(case_bucket="top_docs_worse"),
            docs_better.assign(case_bucket="top_docs_better"),
            ties.assign(case_bucket="top_ties_largest_prompt_expansion"),
        ],
        ignore_index=True,
    )
    return selected[["case_bucket", *columns]]


def build_summary_by_problem(pairs: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        pairs.groupby("summary_docs", dropna=False)
        .agg(
            n_pairs=("specific_oid", "count"),
            docs_worse_line=("line_outcome", lambda s: int((s == "docs_worse").sum())),
            docs_better_line=("line_outcome", lambda s: int((s == "docs_better").sum())),
            ties_line=("line_outcome", lambda s: int((s == "tie").sum())),
            mean_delta_prompt_chars=("delta_prompt_chars", "mean"),
        )
        .reset_index()
        .rename(columns={"summary_docs": "summary"})
    )
    grouped["net_docs_worse_line"] = grouped["docs_worse_line"] - grouped["docs_better_line"]
    grouped = grouped.sort_values(
        ["net_docs_worse_line", "docs_worse_line", "n_pairs", "mean_delta_prompt_chars"],
        ascending=[False, False, False, False],
    )
    return grouped


def format_pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value * 100:.2f}%"


def format_float(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.4f}"


def build_markdown_report(
    iteration_id: int,
    summary_df: pd.DataFrame,
    spearman_df: pd.DataFrame,
    pair_spearman_df: pd.DataFrame,
    pairs: pd.DataFrame,
    interesting_df: pd.DataFrame,
    summary_by_problem_df: pd.DataFrame,
) -> str:
    variant_summary = summary_df[summary_df["scope"] == "variant"].set_index("scope_value")
    overall_line = spearman_df[
        (spearman_df["scope"] == "all")
        & (spearman_df["size_metric"] == "prompt_chars")
        & (spearman_df["success_metric"] == "line_success")
    ].iloc[0]
    overall_block = spearman_df[
        (spearman_df["scope"] == "all")
        & (spearman_df["size_metric"] == "prompt_chars")
        & (spearman_df["success_metric"] == "block_strict_success")
    ].iloc[0]
    docs_block = spearman_df[
        (spearman_df["scope"] == "variant")
        & (spearman_df["scope_value"] == "docs")
        & (spearman_df["size_metric"] == "prompt_chars")
        & (spearman_df["success_metric"] == "block_strict_success")
    ].iloc[0]
    snippet_block = spearman_df[
        (spearman_df["scope"] == "variant")
        & (spearman_df["scope_value"] == "snippet")
        & (spearman_df["size_metric"] == "prompt_chars")
        & (spearman_df["success_metric"] == "block_strict_success")
    ].iloc[0]
    pair_line = pair_spearman_df[
        (pair_spearman_df["scope"] == "all")
        & (pair_spearman_df["size_metric"] == "delta_prompt_chars")
        & (pair_spearman_df["success_metric"] == "delta_line_success")
    ].iloc[0]
    strongest_block = (
        spearman_df[
            (spearman_df["scope"] == "all")
            & (spearman_df["success_metric"] == "block_strict_success")
            & (spearman_df["size_metric"].isin(SIZE_METRICS))
        ]
        .assign(abs_rho=lambda d: d["rho"].abs())
        .sort_values(["abs_rho", "p_value"], ascending=[False, True])
        .iloc[0]
    )

    docs_worse = int((pairs["line_outcome"] == "docs_worse").sum())
    docs_better = int((pairs["line_outcome"] == "docs_better").sum())
    ties = int((pairs["line_outcome"] == "tie").sum())
    docs_chars = variant_summary.loc["docs", "prompt_chars_mean"]
    snippet_chars = variant_summary.loc["snippet", "prompt_chars_mean"]
    docs_to_snippet_ratio = docs_chars / snippet_chars if snippet_chars else np.nan

    top_problem_rows = summary_by_problem_df.head(5)
    top_problem_md = top_problem_rows.to_markdown(index=False)

    interesting_md = interesting_df[
        [
            "case_bucket",
            "model",
            "specific_oid",
            "summary_docs",
            "delta_prompt_chars",
            "line_success_docs",
            "line_success_snippet",
            "block_strict_success_docs",
            "block_strict_success_snippet",
        ]
    ].rename(columns={"summary_docs": "summary"}).to_markdown(index=False)

    return f"""# Prompt Size Effect Analysis (Iteration {iteration_id})

## Scope

- Dataset size: {int(summary_df.loc[summary_df["scope"] == "all", "n"].iloc[0])} matched iteration-{iteration_id} attempts across four model families and two prompt styles.
- Prompt styles: `snippet` = local Terraform block only, `docs` = local block plus schema/documentation context.
- Prompt-size proxies: characters, words, and lines. The main tables below use Spearman correlation because the relationship is monotonic/non-parametric and the success labels are binary.

## Descriptive comparison

- `docs` mean prompt length: {variant_summary.loc["docs", "prompt_chars_mean"]:.1f} chars; median: {variant_summary.loc["docs", "prompt_chars_median"]:.1f}.
- `snippet` mean prompt length: {variant_summary.loc["snippet", "prompt_chars_mean"]:.1f} chars; median: {variant_summary.loc["snippet", "prompt_chars_median"]:.1f}.
- Mean prompt expansion from `snippet` to `docs`: {docs_to_snippet_ratio:.2f}x.
- `docs` iteration-{iteration_id} line-success rate: {format_pct(variant_summary.loc["docs", "line_success_rate"])}.
- `snippet` iteration-{iteration_id} line-success rate: {format_pct(variant_summary.loc["snippet", "line_success_rate"])}.
- `docs` iteration-{iteration_id} block-strict success rate: {format_pct(variant_summary.loc["docs", "block_strict_success_rate"])}.
- `snippet` iteration-{iteration_id} block-strict success rate: {format_pct(variant_summary.loc["snippet", "block_strict_success_rate"])}.

## Spearman findings

- Overall `prompt_chars` vs `line_success`: rho = {format_float(overall_line["rho"])}, p = {format_float(overall_line["p_value"])}.
- Overall `prompt_chars` vs `block_strict_success`: rho = {format_float(overall_block["rho"])}, p = {format_float(overall_block["p_value"])}.
- Within `docs`, `prompt_chars` vs `block_strict_success`: rho = {format_float(docs_block["rho"])}, p = {format_float(docs_block["p_value"])}.
- Within `snippet`, `prompt_chars` vs `block_strict_success`: rho = {format_float(snippet_block["rho"])}, p = {format_float(snippet_block["p_value"])}.
- Paired docs-minus-snippet prompt expansion vs paired line-success delta: rho = {format_float(pair_line["rho"])}, p = {format_float(pair_line["p_value"])}.
- Strongest overall size proxy for block-strict success: `{strongest_block["size_metric"]}` with rho = {format_float(strongest_block["rho"])}, p = {format_float(strongest_block["p_value"])}.

Interpretation:

- The aggregate association is negative, but small. Longer prompts correlate with lower success, especially for the stricter block-level metric.
- The paired delta analysis is weak, which means prompt length alone does not fully explain why docs helps or hurts on a matched instance.
- This supports a careful claim: prompt size appears to be one contributing factor, but it is entangled with instance difficulty and with the semantic effect of adding schema text.

## Paired outcome counts

- Docs worse than snippet on line success: {docs_worse} pairs.
- Docs better than snippet on line success: {docs_better} pairs.
- Tied on line success: {ties} pairs.

## Problem summaries with the most docs-worse pairs

{top_problem_md}

## Interesting matched instances

{interesting_md}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze prompt-size effects on iteration-level repair success.")
    parser.add_argument("--iteration-id", type=int, default=1, help="Iteration to analyze.")
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/prompt_size_effect",
        help="Directory for generated CSV and Markdown outputs.",
    )
    parser.add_argument("--top-n", type=int, default=12, help="Cases to keep per interesting-case bucket.")
    args = parser.parse_args()

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"iteration_{args.iteration_id}"

    records = load_iteration_records(args.iteration_id)
    summary = summarize_iteration_records(records)
    spearman = build_spearman_summary(records)
    pairs = build_paired_records(records)
    pair_spearman = build_pair_delta_spearman(pairs)
    interesting = build_interesting_cases(pairs, args.top_n)
    summary_by_problem = build_summary_by_problem(pairs)
    report = build_markdown_report(
        iteration_id=args.iteration_id,
        summary_df=summary,
        spearman_df=spearman,
        pair_spearman_df=pair_spearman,
        pairs=pairs,
        interesting_df=interesting,
        summary_by_problem_df=summary_by_problem,
    )

    records_path = output_dir / f"{suffix}_records.csv"
    summary_path = output_dir / f"{suffix}_summary.csv"
    spearman_path = output_dir / f"{suffix}_spearman.csv"
    pairs_path = output_dir / f"{suffix}_paired_records.csv"
    pair_spearman_path = output_dir / f"{suffix}_pair_delta_spearman.csv"
    interesting_path = output_dir / f"{suffix}_interesting_cases.csv"
    problem_summary_path = output_dir / f"{suffix}_problem_summary.csv"
    report_path = output_dir / f"{suffix}_report.md"

    records.to_csv(records_path, index=False)
    summary.to_csv(summary_path, index=False)
    spearman.to_csv(spearman_path, index=False)
    pairs.to_csv(pairs_path, index=False)
    pair_spearman.to_csv(pair_spearman_path, index=False)
    interesting.to_csv(interesting_path, index=False)
    summary_by_problem.to_csv(problem_summary_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {records_path}")
    print(f"[OK] wrote {summary_path}")
    print(f"[OK] wrote {spearman_path}")
    print(f"[OK] wrote {pairs_path}")
    print(f"[OK] wrote {pair_spearman_path}")
    print(f"[OK] wrote {interesting_path}")
    print(f"[OK] wrote {problem_summary_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
