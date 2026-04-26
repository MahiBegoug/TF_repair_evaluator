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


def load_model_instances(model_name: str, spec: dict, iteration_id: int) -> pd.DataFrame:
    responses = pd.read_csv(resolve_path(spec["responses_csv"]))
    results = pd.read_csv(resolve_path(spec["results_csv"]))

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    responses = responses[responses["iteration_id"] == iteration_id].copy()
    results = results[results["iteration_id"] == iteration_id].copy()

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
        "oid",
        "benchmark_oid",
        "filename",
        "line_start",
        "line_end",
        "severity",
        "summary",
        "detail",
        "llm_name",
        "prompt_chars",
        "line_specific_error_fixed",
        "block_fix_introduced_errors",
        "block_strict_success",
    ]
    available_keep = [column for column in keep if column in merged.columns]
    return merged[available_keep].sort_values(["specific_oid"]).reset_index(drop=True)


def build_correlation(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, group in df.groupby("model", sort=False):
        rho, p_value = safe_spearman(group["prompt_chars"], group["block_strict_success"])
        rows.append(
            {
                "scope": "model",
                "scope_value": model,
                "n": len(group),
                "mean_prompt_chars": group["prompt_chars"].mean(),
                "median_prompt_chars": group["prompt_chars"].median(),
                "block_strict_success_rate": group["block_strict_success"].mean(),
                "rho_prompt_chars_vs_block_strict_success": rho,
                "p_value": p_value,
            }
        )

    rho_all, p_all = safe_spearman(df["prompt_chars"], df["block_strict_success"])
    rows.append(
        {
            "scope": "all_models",
            "scope_value": "all_models",
            "n": len(df),
            "mean_prompt_chars": df["prompt_chars"].mean(),
            "median_prompt_chars": df["prompt_chars"].median(),
            "block_strict_success_rate": df["block_strict_success"].mean(),
            "rho_prompt_chars_vs_block_strict_success": rho_all,
            "p_value": p_all,
        }
    )
    return pd.DataFrame(rows)


def build_report(corr_df: pd.DataFrame, iteration_id: int) -> str:
    return "\n".join(
        [
            f"# Docs Prompt Chars vs Block-Strict Success (Iteration {iteration_id})",
            "",
            corr_df.to_markdown(index=False),
            "",
            "## Interpretation",
            "",
            "- The tested relationship is `prompt_chars` versus binary `block_strict_success`.",
            "- `block_strict_success = 1` iff `line_specific_error_fixed == 1` and `block_fix_introduced_errors == 0`.",
            "- Negative rho means larger prompts in characters are associated with lower strict block-level success.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze docs prompt chars against block-strict success for iteration 1.")
    parser.add_argument("--iteration-id", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/tests/docs_prompt_chars_block_strict_iter1",
        help="Directory for generated outputs.",
    )
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for model_name, spec in MODEL_SPECS.items():
        frames.append(load_model_instances(model_name, spec, args.iteration_id))

    instances = pd.concat(frames, ignore_index=True)
    correlations = build_correlation(instances)
    report = build_report(correlations, args.iteration_id)

    instances_path = output_dir / "docs_iter1_block_strict_prompt_chars_per_instance.csv"
    corr_path = output_dir / "docs_iter1_block_strict_prompt_chars_spearman.csv"
    report_path = output_dir / "docs_iter1_block_strict_prompt_chars_report.md"

    instances.to_csv(instances_path, index=False)
    correlations.to_csv(corr_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {instances_path}")
    print(f"[OK] wrote {corr_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
