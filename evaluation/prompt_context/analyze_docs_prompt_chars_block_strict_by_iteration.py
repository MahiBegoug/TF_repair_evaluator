import argparse
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]

MODEL_SPECS = {
    "CodeLlama_34b_Instruct_hf": {
        "responses_csv": "llm_responses/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv",
    },
    "Codestral_22B_v0.1": {
        "responses_csv": "llm_responses/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml_repair_results.csv",
    },
    "deepseek_coder_33b_instruct": {
        "responses_csv": "llm_responses/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml_repair_results.csv",
    },
    "gpt_oss_20b": {
        "responses_csv": "llm_responses/gpt_oss_20b_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/gpt_oss_20b_docs_snippet_marked_code_only_xml_repair_results.csv",
    },
}


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


def load_instances(model_name: str, spec: dict) -> pd.DataFrame:
    responses = pd.read_csv(resolve_path(spec["responses_csv"]))
    results = pd.read_csv(resolve_path(spec["results_csv"]))

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    prompt_text = responses["prompt_content"].fillna("").astype(str)
    responses["prompt_chars"] = prompt_text.str.len()

    merged = responses.merge(
        results,
        on=["specific_oid", "iteration_id"],
        how="inner",
        suffixes=("_prompt", "_result"),
    )

    for column in ["filename", "llm_name", "project_name", "summary", "detail", "severity", "oid"]:
        prompt_col = f"{column}_prompt"
        result_col = f"{column}_result"
        if column not in merged.columns:
            if prompt_col in merged.columns:
                merged[column] = merged[prompt_col]
            elif result_col in merged.columns:
                merged[column] = merged[result_col]

    merged["model"] = model_name
    merged["block_strict_success"] = (
        merged["line_specific_error_fixed"].fillna(False).astype(bool)
        & (merged["block_fix_introduced_errors"].fillna(0).astype(int) == 0)
    ).astype(int)

    keep = [
        "model",
        "specific_oid",
        "iteration_id",
        "project_name",
        "filename",
        "summary",
        "prompt_chars",
        "line_specific_error_fixed",
        "block_fix_introduced_errors",
        "block_strict_success",
    ]
    available_keep = [column for column in keep if column in merged.columns]
    return merged[available_keep].copy()


def build_iteration_correlation(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, model_group in df.groupby("model", sort=False):
        for iteration_id, group in model_group.groupby("iteration_id", sort=True):
            rho, p_value = safe_spearman(group["prompt_chars"], group["block_strict_success"])
            rows.append(
                {
                    "model": model,
                    "iteration_id": int(iteration_id),
                    "n": len(group),
                    "mean_prompt_chars": group["prompt_chars"].mean(),
                    "median_prompt_chars": group["prompt_chars"].median(),
                    "block_strict_success_rate": group["block_strict_success"].mean(),
                    "rho_prompt_chars_vs_block_strict_success": rho,
                    "p_value": p_value,
                    "significant_0_05": bool(pd.notna(p_value) and p_value < 0.05),
                }
            )
    return pd.DataFrame(rows)


def build_significance_summary(corr_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        corr_df.groupby("model", sort=False)
        .agg(
            significant_iterations=("significant_0_05", "sum"),
            min_p_value=("p_value", "min"),
            most_negative_rho=("rho_prompt_chars_vs_block_strict_success", "min"),
            mean_success_rate=("block_strict_success_rate", "mean"),
        )
        .reset_index()
        .sort_values(["significant_iterations", "min_p_value"], ascending=[False, True])
    )
    return summary


def build_report(corr_df: pd.DataFrame, summary_df: pd.DataFrame) -> str:
    lines = [
        "# Docs Prompt Chars vs Block-Strict Success By Iteration",
        "",
        "## Significance summary",
        "",
        summary_df.to_markdown(index=False),
        "",
        "## Iteration-level results",
        "",
        corr_df.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "- The tested relationship is `prompt_chars` versus binary `block_strict_success`.",
        "- `block_strict_success = 1` iff `line_specific_error_fixed == 1` and `block_fix_introduced_errors == 0`.",
        "- Each row uses one iteration only, so this tests whether larger docs prompts are associated with lower strict success within that iteration for that model.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze docs prompt chars vs block-strict success for each iteration and model.")
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/tests/docs_prompt_chars_block_strict_by_iteration",
        help="Directory for generated outputs.",
    )
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for model_name, spec in MODEL_SPECS.items():
        frames.append(load_instances(model_name, spec))

    instances = pd.concat(frames, ignore_index=True)
    corr_df = build_iteration_correlation(instances)
    summary_df = build_significance_summary(corr_df)
    report = build_report(corr_df, summary_df)

    instances_path = output_dir / "docs_block_strict_prompt_chars_all_iterations_per_instance.csv"
    corr_path = output_dir / "docs_block_strict_prompt_chars_by_iteration.csv"
    summary_path = output_dir / "docs_block_strict_prompt_chars_significance_summary.csv"
    report_path = output_dir / "docs_block_strict_prompt_chars_by_iteration_report.md"

    instances.to_csv(instances_path, index=False)
    corr_df.to_csv(corr_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {instances_path}")
    print(f"[OK] wrote {corr_path}")
    print(f"[OK] wrote {summary_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
