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

SIZE_METRICS = ["prompt_tokens", "prompt_chars", "prompt_words", "prompt_lines"]
SUCCESS_METRICS = ["line_success", "block_strict_success", "module_strict_success"]


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


def load_model_instances(model_name: str, spec: dict, iteration_id: int, batch_size: int) -> pd.DataFrame:
    responses = pd.read_csv(resolve_path(spec["responses_csv"]))
    results = pd.read_csv(resolve_path(spec["results_csv"]))

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    responses = responses[responses["iteration_id"] == iteration_id].copy()
    results = results[results["iteration_id"] == iteration_id].copy()

    tokenizer = AutoTokenizer.from_pretrained(spec["tokenizer"], use_fast=True)
    prompt_text = responses["prompt_content"].fillna("").astype(str)
    responses["prompt_tokens"] = compute_token_lengths(prompt_text.tolist(), tokenizer, batch_size)
    responses["prompt_chars"] = prompt_text.str.len()
    responses["prompt_words"] = prompt_text.str.split().str.len()
    responses["prompt_lines"] = prompt_text.str.count("\n") + 1

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
    merged["line_success"] = merged["line_specific_error_fixed"].fillna(False).astype(bool).astype(int)
    merged["block_strict_success"] = (
        merged["line_specific_error_fixed"].fillna(False).astype(bool)
        & (merged["block_fix_introduced_errors"].fillna(0).astype(int) == 0)
    ).astype(int)
    merged["module_strict_success"] = (
        merged["line_specific_error_fixed"].fillna(False).astype(bool)
        & (merged["module_fix_introduced_errors"].fillna(0).astype(int) == 0)
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
        "prompt_chars",
        "prompt_words",
        "prompt_lines",
        "is_fixed",
        "line_is_clean",
        "line_specific_error_fixed",
        "line_success",
        "block_fix_introduced_errors",
        "block_strict_success",
        "module_fix_introduced_errors",
        "module_strict_success",
    ]
    available_keep = [column for column in keep if column in merged.columns]
    return merged[available_keep].sort_values(["specific_oid"]).reset_index(drop=True)


def build_correlation_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, group in df.groupby("model", sort=False):
        for size_metric in SIZE_METRICS:
            for success_metric in SUCCESS_METRICS:
                rho, p_value = safe_spearman(group[size_metric], group[success_metric])
                rows.append(
                    {
                        "model": model,
                        "size_metric": size_metric,
                        "success_metric": success_metric,
                        "n": len(group),
                        "rho": rho,
                        "p_value": p_value,
                    }
                )
    return pd.DataFrame(rows)


def build_model_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("model", sort=False)
        .agg(
            n=("specific_oid", "count"),
            mean_prompt_tokens=("prompt_tokens", "mean"),
            median_prompt_tokens=("prompt_tokens", "median"),
            min_prompt_tokens=("prompt_tokens", "min"),
            max_prompt_tokens=("prompt_tokens", "max"),
            mean_prompt_chars=("prompt_chars", "mean"),
            line_success_rate=("line_success", "mean"),
            block_strict_success_rate=("block_strict_success", "mean"),
            module_strict_success_rate=("module_strict_success", "mean"),
        )
        .reset_index()
    )
    return summary


def build_quartiles(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, group in df.groupby("model", sort=False):
        work = group.copy()
        work["token_quartile"] = pd.qcut(
            work["prompt_tokens"],
            q=4,
            labels=["Q1", "Q2", "Q3", "Q4"],
            duplicates="drop",
        )
        quartiles = (
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
        quartiles.insert(0, "model", model)
        rows.append(quartiles)
    return pd.concat(rows, ignore_index=True)


def format_float(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.4f}"


def format_pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value * 100:.2f}%"


def build_report(summary_df: pd.DataFrame, corr_df: pd.DataFrame) -> str:
    lines = [
        "# Eval-1 Docs Prompt Tokens Across Models",
        "",
        "## Per-model summary",
        "",
        summary_df.to_markdown(index=False),
        "",
        "## Per-model Spearman highlights",
        "",
    ]

    for model in summary_df["model"]:
        subset = corr_df[
            (corr_df["model"] == model)
            & (corr_df["size_metric"] == "prompt_tokens")
        ].copy()
        token_line = subset[subset["success_metric"] == "line_success"].iloc[0]
        token_block = subset[subset["success_metric"] == "block_strict_success"].iloc[0]
        token_module = subset[subset["success_metric"] == "module_strict_success"].iloc[0]
        strongest = (
            corr_df[corr_df["model"] == model]
            .assign(abs_rho=lambda d: d["rho"].abs())
            .sort_values(["abs_rho", "p_value"], ascending=[False, True])
            .iloc[0]
        )
        lines.extend(
            [
                f"### {model}",
                "",
                f"- Mean prompt tokens: {summary_df.loc[summary_df['model'] == model, 'mean_prompt_tokens'].iloc[0]:.2f}",
                f"- Line success rate: {format_pct(summary_df.loc[summary_df['model'] == model, 'line_success_rate'].iloc[0])}",
                f"- Block-strict success rate: {format_pct(summary_df.loc[summary_df['model'] == model, 'block_strict_success_rate'].iloc[0])}",
                f"- `prompt_tokens` vs `line_success`: rho = {format_float(token_line['rho'])}, p = {format_float(token_line['p_value'])}",
                f"- `prompt_tokens` vs `block_strict_success`: rho = {format_float(token_block['rho'])}, p = {format_float(token_block['p_value'])}",
                f"- `prompt_tokens` vs `module_strict_success`: rho = {format_float(token_module['rho'])}, p = {format_float(token_module['p_value'])}",
                f"- Strongest size/success association: `{strongest['size_metric']}` vs `{strongest['success_metric']}` with rho = {format_float(strongest['rho'])}, p = {format_float(strongest['p_value'])}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-model eval-1 docs prompt token analysis across all models.")
    parser.add_argument("--iteration-id", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/prompt_tokens/all_models_eval1_docs",
        help="Directory for generated outputs.",
    )
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    for model_name, spec in MODEL_SPECS.items():
        frames.append(load_model_instances(model_name, spec, args.iteration_id, args.batch_size))

    instances = pd.concat(frames, ignore_index=True)
    summary = build_model_summary(instances)
    correlations = build_correlation_table(instances)
    quartiles = build_quartiles(instances)
    report = build_report(summary, correlations)

    instances_path = output_dir / "eval1_docs_prompt_tokens_per_instance.csv"
    summary_path = output_dir / "eval1_docs_prompt_tokens_per_model_summary.csv"
    corr_path = output_dir / "eval1_docs_prompt_tokens_per_model_spearman.csv"
    quartiles_path = output_dir / "eval1_docs_prompt_tokens_per_model_quartiles.csv"
    report_path = output_dir / "eval1_docs_prompt_tokens_report.md"

    instances.to_csv(instances_path, index=False)
    summary.to_csv(summary_path, index=False)
    correlations.to_csv(corr_path, index=False)
    quartiles.to_csv(quartiles_path, index=False)
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] wrote {instances_path}")
    print(f"[OK] wrote {summary_path}")
    print(f"[OK] wrote {corr_path}")
    print(f"[OK] wrote {quartiles_path}")
    print(f"[OK] wrote {report_path}")


if __name__ == "__main__":
    main()
