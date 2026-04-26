import argparse
from pathlib import Path

import pandas as pd
from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a prompt-token dataset by merging raw prompts with existing repair results."
    )
    parser.add_argument(
        "--responses-csv",
        default="llm_responses/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv",
        help="Raw LLM response CSV containing prompt_content.",
    )
    parser.add_argument(
        "--results-csv",
        default="llms_fixes_results/eval_1_completed_from_prior/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv",
        help="Repair-results CSV to merge against.",
    )
    parser.add_argument(
        "--tokenizer",
        default="codellama/CodeLlama-34b-Instruct-hf",
        help="Hugging Face tokenizer id used to count prompt tokens.",
    )
    parser.add_argument(
        "--iteration-id",
        type=int,
        default=1,
        help="Only keep this iteration id.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Tokenizer batch size.",
    )
    parser.add_argument(
        "--output-csv",
        default="evaluation/results/prompt_tokens/CodeLlama_34b_Instruct_hf_docs_eval1_prompt_tokens.csv",
        help="Output CSV path.",
    )
    args = parser.parse_args()

    responses_path = resolve_path(args.responses_csv)
    results_path = resolve_path(args.results_csv)
    output_path = resolve_path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    responses = pd.read_csv(responses_path)
    results = pd.read_csv(results_path)

    responses["specific_oid"] = responses["specific_oid"].astype(str)
    responses["iteration_id"] = responses["iteration_id"].astype(int)
    results["specific_oid"] = results["specific_oid"].astype(str)
    results["iteration_id"] = results["iteration_id"].astype(int)

    responses = responses[responses["iteration_id"] == args.iteration_id].copy()
    results = results[results["iteration_id"] == args.iteration_id].copy()

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    prompt_text = responses["prompt_content"].fillna("").astype(str).tolist()
    responses["prompt_tokens"] = compute_token_lengths(prompt_text, tokenizer, args.batch_size)
    responses["prompt_chars"] = responses["prompt_content"].fillna("").astype(str).str.len()
    responses["prompt_words"] = responses["prompt_content"].fillna("").astype(str).str.split().str.len()
    responses["prompt_lines"] = responses["prompt_content"].fillna("").astype(str).str.count("\n") + 1

    merged = responses.merge(
        results,
        on=["specific_oid", "iteration_id"],
        how="inner",
        suffixes=("_prompt", "_result"),
    )

    for column in ["filename", "llm_name"]:
        prompt_col = f"{column}_prompt"
        result_col = f"{column}_result"
        if column not in merged.columns:
            if prompt_col in merged.columns:
                merged[column] = merged[prompt_col]
            elif result_col in merged.columns:
                merged[column] = merged[result_col]

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
    dataset = merged[available_keep].sort_values(["specific_oid", "iteration_id"]).reset_index(drop=True)
    dataset.to_csv(output_path, index=False)

    print(f"[OK] wrote {output_path}")
    print(f"[INFO] rows={len(dataset)}")
    print(f"[INFO] mean_prompt_tokens={dataset['prompt_tokens'].mean():.2f}")
    print(f"[INFO] median_prompt_tokens={dataset['prompt_tokens'].median():.2f}")
    print(f"[INFO] line_success_rate={dataset['line_success'].mean():.4f}")
    print(f"[INFO] block_strict_success_rate={dataset['block_strict_success'].mean():.4f}")
    print(f"[INFO] module_strict_success_rate={dataset['module_strict_success'].mean():.4f}")


if __name__ == "__main__":
    main()
