import argparse
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest


ROOT = Path(__file__).resolve().parents[2]

MODEL_SPECS = {
    "CodeLlama_34b_Instruct_hf": {
        "docs_responses_csv": "llm_responses/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv",
        "snippet_responses_csv": "llm_responses/CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml.csv",
        "docs_results_csv": "llms_fixes_results/eval_1_completed_from_prior/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet_results_csv": "llms_fixes_results/eval_1_completed_from_prior/CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml_repair_results.csv",
    },
    "Codestral_22B_v0.1": {
        "docs_responses_csv": "llm_responses/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml.csv",
        "snippet_responses_csv": "llm_responses/Codestral_22B_v0.1_snippet_marked_code_only_xml.csv",
        "docs_results_csv": "llms_fixes_results/eval_1_completed_from_prior/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet_results_csv": "llms_fixes_results/eval_1_completed_from_prior/Codestral_22B_v0.1_snippet_marked_code_only_xml_repair_results.csv",
    },
    "deepseek_coder_33b_instruct": {
        "docs_responses_csv": "llm_responses/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml.csv",
        "snippet_responses_csv": "llm_responses/deepseek_coder_33b_instruct_snippet_marked_code_only_xml.csv",
        "docs_results_csv": "llms_fixes_results/eval_1_completed_from_prior/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet_results_csv": "llms_fixes_results/eval_1_completed_from_prior/deepseek_coder_33b_instruct_snippet_marked_code_only_xml_repair_results.csv",
    },
    "gpt_oss_20b": {
        "docs_responses_csv": "llm_responses/gpt_oss_20b_docs_snippet_marked_code_only_xml.csv",
        "snippet_responses_csv": "llm_responses/gpt_oss_20b_snippet_marked_code_only_xml.csv",
        "docs_results_csv": "llms_fixes_results/eval_1_completed_from_prior/gpt_oss_20b_docs_snippet_marked_code_only_xml_repair_results.csv",
        "snippet_results_csv": "llms_fixes_results/eval_1_completed_from_prior/gpt_oss_20b_snippet_marked_code_only_xml_repair_results.csv",
    },
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def load_variant_pair(response_path: Path, result_path: Path, variant: str) -> pd.DataFrame:
    responses = pd.read_csv(response_path)
    results = pd.read_csv(result_path)

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    responses["prompt_chars"] = responses["prompt_content"].fillna("").astype(str).str.len()

    merged = responses.merge(
        results,
        on=["specific_oid", "iteration_id"],
        how="inner",
        suffixes=("_prompt", "_result"),
    )

    for column in ["project_name", "filename", "summary", "detail", "severity"]:
        prompt_col = f"{column}_prompt"
        result_col = f"{column}_result"
        if column not in merged.columns:
            if prompt_col in merged.columns:
                merged[column] = merged[prompt_col]
            elif result_col in merged.columns:
                merged[column] = merged[result_col]
            else:
                merged[column] = ""

    merged[f"{variant}_block_strict_success"] = (
        merged["line_specific_error_fixed"].fillna(False).astype(bool)
        & (merged["block_fix_introduced_errors"].fillna(0).astype(int) == 0)
    ).astype(int)

    keep = [
        "specific_oid",
        "iteration_id",
        "project_name",
        "filename",
        "summary",
        "detail",
        "severity",
        "prompt_chars",
        f"{variant}_block_strict_success",
    ]
    subset = merged[keep].copy()
    subset = subset.rename(columns={"prompt_chars": f"{variant}_prompt_chars"})
    return subset


def exact_mcnemar_pvalue(docs_worse: int, docs_better: int) -> float:
    discordant = docs_worse + docs_better
    if discordant == 0:
        return 1.0
    return float(binomtest(min(docs_worse, docs_better), n=discordant, p=0.5, alternative="two-sided").pvalue)


def build_paired_records() -> pd.DataFrame:
    frames = []
    for model_name, spec in MODEL_SPECS.items():
        docs_df = load_variant_pair(
            resolve_path(spec["docs_responses_csv"]),
            resolve_path(spec["docs_results_csv"]),
            "docs",
        )
        snippet_df = load_variant_pair(
            resolve_path(spec["snippet_responses_csv"]),
            resolve_path(spec["snippet_results_csv"]),
            "snippet",
        )
        paired = docs_df.merge(
            snippet_df,
            on=["specific_oid", "iteration_id"],
            how="inner",
            suffixes=("_docs_meta", "_snippet_meta"),
        )
        for column in ["project_name", "filename", "summary", "detail", "severity"]:
            docs_col = f"{column}_docs_meta"
            snippet_col = f"{column}_snippet_meta"
            if docs_col in paired.columns:
                paired[column] = paired[docs_col]
            elif snippet_col in paired.columns:
                paired[column] = paired[snippet_col]

        paired["model"] = model_name
        paired["delta_prompt_chars"] = paired["docs_prompt_chars"] - paired["snippet_prompt_chars"]
        paired["delta_block_strict_success"] = (
            paired["docs_block_strict_success"] - paired["snippet_block_strict_success"]
        )
        paired["docs_worse"] = (
            (paired["docs_block_strict_success"] == 0) & (paired["snippet_block_strict_success"] == 1)
        ).astype(int)
        paired["docs_better"] = (
            (paired["docs_block_strict_success"] == 1) & (paired["snippet_block_strict_success"] == 0)
        ).astype(int)
        paired["both_success"] = (
            (paired["docs_block_strict_success"] == 1) & (paired["snippet_block_strict_success"] == 1)
        ).astype(int)
        paired["both_fail"] = (
            (paired["docs_block_strict_success"] == 0) & (paired["snippet_block_strict_success"] == 0)
        ).astype(int)
        frames.append(
            paired[
                [
                    "model",
                    "specific_oid",
                    "iteration_id",
                    "project_name",
                    "filename",
                    "summary",
                    "detail",
                    "severity",
                    "docs_prompt_chars",
                    "snippet_prompt_chars",
                    "delta_prompt_chars",
                    "docs_block_strict_success",
                    "snippet_block_strict_success",
                    "delta_block_strict_success",
                    "docs_worse",
                    "docs_better",
                    "both_success",
                    "both_fail",
                ]
            ]
        )
    return pd.concat(frames, ignore_index=True)


def summarize_pairs(df: pd.DataFrame, scope_label: str) -> pd.DataFrame:
    rows = []
    grouped = list(df.groupby("model", sort=False))
    grouped.append(("all_models", df))

    for model_name, group in grouped:
        docs_worse = int(group["docs_worse"].sum())
        docs_better = int(group["docs_better"].sum())
        both_success = int(group["both_success"].sum())
        both_fail = int(group["both_fail"].sum())
        discordant = docs_worse + docs_better
        rows.append(
            {
                "scope": scope_label,
                "model": model_name,
                "n_pairs": len(group),
                "mean_docs_prompt_chars": group["docs_prompt_chars"].mean(),
                "mean_snippet_prompt_chars": group["snippet_prompt_chars"].mean(),
                "mean_delta_prompt_chars": group["delta_prompt_chars"].mean(),
                "docs_block_strict_success_rate": group["docs_block_strict_success"].mean(),
                "snippet_block_strict_success_rate": group["snippet_block_strict_success"].mean(),
                "delta_docs_minus_snippet_pp": (group["docs_block_strict_success"].mean() - group["snippet_block_strict_success"].mean()) * 100.0,
                "docs_worse_count": docs_worse,
                "docs_better_count": docs_better,
                "both_success_count": both_success,
                "both_fail_count": both_fail,
                "discordant_pairs": discordant,
                "docs_worse_share_of_discordant": (docs_worse / discordant) if discordant else 0.0,
                "exact_mcnemar_p_value": exact_mcnemar_pvalue(docs_worse, docs_better),
            }
        )

    return pd.DataFrame(rows)


def summarize_by_iteration(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model_name, iteration_id), group in df.groupby(["model", "iteration_id"], sort=False):
        docs_worse = int(group["docs_worse"].sum())
        docs_better = int(group["docs_better"].sum())
        discordant = docs_worse + docs_better
        rows.append(
            {
                "model": model_name,
                "iteration_id": int(iteration_id),
                "n_pairs": len(group),
                "mean_delta_prompt_chars": group["delta_prompt_chars"].mean(),
                "docs_block_strict_success_rate": group["docs_block_strict_success"].mean(),
                "snippet_block_strict_success_rate": group["snippet_block_strict_success"].mean(),
                "delta_docs_minus_snippet_pp": (group["docs_block_strict_success"].mean() - group["snippet_block_strict_success"].mean()) * 100.0,
                "docs_worse_count": docs_worse,
                "docs_better_count": docs_better,
                "discordant_pairs": discordant,
                "exact_mcnemar_p_value": exact_mcnemar_pvalue(docs_worse, docs_better),
                "significant_0_05": bool(discordant and exact_mcnemar_pvalue(docs_worse, docs_better) < 0.05),
            }
        )
    return pd.DataFrame(rows)


def summarize_all_models_by_iteration(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for iteration_id, group in df.groupby("iteration_id", sort=True):
        docs_worse = int(group["docs_worse"].sum())
        docs_better = int(group["docs_better"].sum())
        discordant = docs_worse + docs_better
        rows.append(
            {
                "iteration_id": int(iteration_id),
                "n_pairs": len(group),
                "mean_delta_prompt_chars": group["delta_prompt_chars"].mean(),
                "docs_block_strict_success_rate": group["docs_block_strict_success"].mean(),
                "snippet_block_strict_success_rate": group["snippet_block_strict_success"].mean(),
                "delta_docs_minus_snippet_pp": (group["docs_block_strict_success"].mean() - group["snippet_block_strict_success"].mean()) * 100.0,
                "docs_worse_count": docs_worse,
                "docs_better_count": docs_better,
                "discordant_pairs": discordant,
                "exact_mcnemar_p_value": exact_mcnemar_pvalue(docs_worse, docs_better),
                "significant_0_05": bool(discordant and exact_mcnemar_pvalue(docs_worse, docs_better) < 0.05),
            }
        )
    return pd.DataFrame(rows)


def build_report(
    iter1_summary: pd.DataFrame,
    all_summary: pd.DataFrame,
    by_iteration: pd.DataFrame,
    pooled_by_iteration: pd.DataFrame,
) -> str:
    sig_by_iteration = (
        by_iteration.groupby("model", sort=False)["significant_0_05"]
        .sum()
        .reset_index()
        .rename(columns={"significant_0_05": "significant_iterations"})
    )
    return "\n".join(
        [
            "# Paired Docs vs Snippet Block-Strict Analysis",
            "",
            "## Iteration 1 summary",
            "",
            iter1_summary.to_markdown(index=False),
            "",
            "## All-iterations summary",
            "",
            all_summary.to_markdown(index=False),
            "",
            "## Significant per-iteration McNemar tests",
            "",
            sig_by_iteration.to_markdown(index=False),
            "",
            "## Pooled all-models by iteration",
            "",
            pooled_by_iteration.to_markdown(index=False),
            "",
            "## Interpretation",
            "",
            "- This is the realistic paired comparison: the same model, same instance, same iteration, with only the prompt condition changed (`docs` vs `snippet`).",
            "- The binary outcome is `block_strict_success = 1` iff `line_specific_error_fixed == 1` and `block_fix_introduced_errors == 0`.",
            "- `docs_worse_count` means `docs = 0` and `snippet = 1` on the same pair.",
            "- `docs_better_count` means `docs = 1` and `snippet = 0` on the same pair.",
            "- The exact McNemar p-value tests whether the discordant-pair imbalance is statistically significant.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired docs-vs-snippet comparison using block-strict success.")
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/tests/docs_vs_snippet_block_strict_paired",
        help="Directory for generated outputs.",
    )
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paired = build_paired_records()
    iter1 = paired[paired["iteration_id"] == 1].copy()

    iter1_summary = summarize_pairs(iter1, "iteration_1")
    all_summary = summarize_pairs(paired, "all_iterations")
    by_iteration = summarize_by_iteration(paired)
    pooled_by_iteration = summarize_all_models_by_iteration(paired)
    report = build_report(iter1_summary, all_summary, by_iteration, pooled_by_iteration)

    paired_path = output_dir / "paired_docs_vs_snippet_block_strict_all_iterations.csv"
    iter1_path = output_dir / "paired_docs_vs_snippet_block_strict_iteration1.csv"
    iter1_summary_path = output_dir / "paired_docs_vs_snippet_block_strict_summary_iteration1.csv"
    all_summary_path = output_dir / "paired_docs_vs_snippet_block_strict_summary_all_iterations.csv"
    by_iteration_path = output_dir / "paired_docs_vs_snippet_block_strict_by_iteration.csv"
    pooled_by_iteration_path = output_dir / "paired_docs_vs_snippet_block_strict_all_models_by_iteration.csv"
    report_path = output_dir / "paired_docs_vs_snippet_block_strict_report.md"

    paired.to_csv(paired_path, index=False)
    iter1.to_csv(iter1_path, index=False)
    iter1_summary.to_csv(iter1_summary_path, index=False)
    all_summary.to_csv(all_summary_path, index=False)
    by_iteration.to_csv(by_iteration_path, index=False)
    pooled_by_iteration.to_csv(pooled_by_iteration_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {paired_path}")
    print(f"[OK] wrote {iter1_path}")
    print(f"[OK] wrote {iter1_summary_path}")
    print(f"[OK] wrote {all_summary_path}")
    print(f"[OK] wrote {by_iteration_path}")
    print(f"[OK] wrote {pooled_by_iteration_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
