import argparse
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr
from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]

MODEL_SPECS = {
    "CodeLlama_34b_Instruct_hf": {
        "responses_csv": "llm_responses/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv",
        "tokenizer": "codellama/CodeLlama-34b-Instruct-hf",
    },
    "Codestral_22B_v0.1": {
        "responses_csv": "llm_responses/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/Codestral_22B_v0.1_docs_snippet_marked_code_only_xml_repair_results.csv",
        "tokenizer": "mistralai/Codestral-22B-v0.1",
    },
    "deepseek_coder_33b_instruct": {
        "responses_csv": "llm_responses/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml_repair_results.csv",
        "tokenizer": "deepseek-ai/deepseek-coder-33b-instruct",
    },
    "gpt_oss_20b": {
        "responses_csv": "llm_responses/gpt_oss_20b_docs_snippet_marked_code_only_xml.csv",
        "results_csv": "llms_fixes_results/eval_1_completed_from_prior/gpt_oss_20b_docs_snippet_marked_code_only_xml_repair_results.csv",
        "tokenizer": "openai/gpt-oss-20b",
    },
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def compute_token_lengths(texts: list[str], tokenizer, batch_size: int) -> list[int]:
    lengths: list[int] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        encoded = tokenizer(
            batch,
            add_special_tokens=False,
            truncation=False,
            padding=False,
        )
        lengths.extend(len(ids) for ids in encoded["input_ids"])
    return lengths


def safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
        return float("nan"), float("nan")
    result = spearmanr(x.astype(float), y.astype(float))
    return float(result.statistic), float(result.pvalue)


def load_model_instances(model_name: str, spec: dict, batch_size: int) -> pd.DataFrame:
    responses = pd.read_csv(resolve_path(spec["responses_csv"]))
    results = pd.read_csv(resolve_path(spec["results_csv"]))

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    tokenizer = AutoTokenizer.from_pretrained(spec["tokenizer"], use_fast=True)
    prompt_text = responses["prompt_content"].fillna("").astype(str)
    responses["prompt_tokens"] = compute_token_lengths(prompt_text.tolist(), tokenizer, batch_size)

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
        "prompt_tokens",
        "line_specific_error_fixed",
        "block_fix_introduced_errors",
        "block_strict_success",
    ]
    available_keep = [column for column in keep if column in merged.columns]
    return merged[available_keep].sort_values(["iteration_id", "specific_oid"]).reset_index(drop=True)


def build_correlation(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, group in df.groupby("model", sort=False):
        rho, p_value = safe_spearman(group["prompt_tokens"], group["block_strict_success"])
        rows.append(
            {
                "scope": "model",
                "scope_value": model,
                "n": len(group),
                "mean_prompt_tokens": group["prompt_tokens"].mean(),
                "median_prompt_tokens": group["prompt_tokens"].median(),
                "block_strict_success_rate": group["block_strict_success"].mean(),
                "rho_prompt_tokens_vs_block_strict_success": rho,
                "p_value": p_value,
            }
        )

    rho_all, p_all = safe_spearman(df["prompt_tokens"], df["block_strict_success"])
    rows.append(
        {
            "scope": "all_models",
            "scope_value": "all_models",
            "n": len(df),
            "mean_prompt_tokens": df["prompt_tokens"].mean(),
            "median_prompt_tokens": df["prompt_tokens"].median(),
            "block_strict_success_rate": df["block_strict_success"].mean(),
            "rho_prompt_tokens_vs_block_strict_success": rho_all,
            "p_value": p_all,
        }
    )
    return pd.DataFrame(rows)


def build_iteration_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["model", "iteration_id"], sort=False)
        .agg(
            n=("specific_oid", "count"),
            mean_prompt_tokens=("prompt_tokens", "mean"),
            median_prompt_tokens=("prompt_tokens", "median"),
            block_strict_success_rate=("block_strict_success", "mean"),
        )
        .reset_index()
    )
    return summary


def build_report(first_corr: pd.DataFrame, all_corr: pd.DataFrame) -> str:
    lines = [
        "# Docs Prompt Tokens vs Block-Strict Success",
        "",
        "## Iteration 1 only",
        "",
        first_corr.to_markdown(index=False),
        "",
        "## All iterations",
        "",
        all_corr.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "- The tested relationship is `prompt_tokens` versus binary `block_strict_success`.",
        "- `block_strict_success = 1` iff `line_specific_error_fixed == 1` and `block_fix_introduced_errors == 0`.",
        "- Negative rho means larger prompts are associated with lower strict block-level success.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze docs prompt tokens against block-strict success for first iteration and all iterations.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/prompt_tokens/docs_block_strict",
        help="Directory for generated outputs.",
    )
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_frames = []
    for model_name, spec in MODEL_SPECS.items():
        all_frames.append(load_model_instances(model_name, spec, args.batch_size))

    all_instances = pd.concat(all_frames, ignore_index=True)
    first_instances = all_instances[all_instances["iteration_id"] == 1].copy()

    first_corr = build_correlation(first_instances)
    all_corr = build_correlation(all_instances)
    iter_summary = build_iteration_summary(all_instances)
    report = build_report(first_corr, all_corr)

    first_instances_path = output_dir / "docs_eval1_block_strict_per_instance.csv"
    all_instances_path = output_dir / "docs_all_iterations_block_strict_per_instance.csv"
    first_corr_path = output_dir / "docs_eval1_block_strict_spearman.csv"
    all_corr_path = output_dir / "docs_all_iterations_block_strict_spearman.csv"
    iter_summary_path = output_dir / "docs_all_iterations_block_strict_iteration_summary.csv"
    report_path = output_dir / "docs_block_strict_prompt_tokens_report.md"

    first_instances.to_csv(first_instances_path, index=False)
    all_instances.to_csv(all_instances_path, index=False)
    first_corr.to_csv(first_corr_path, index=False)
    all_corr.to_csv(all_corr_path, index=False)
    iter_summary.to_csv(iter_summary_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {first_instances_path}")
    print(f"[OK] wrote {all_instances_path}")
    print(f"[OK] wrote {first_corr_path}")
    print(f"[OK] wrote {all_corr_path}")
    print(f"[OK] wrote {iter_summary_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
