"""
Visualize cases where documentation-augmented prompting fails but snippet-only succeeds.

This reuses the same rendering methodology as scripts/visualize_fixes.py:
- same diff generation
- same input/output data sources

Unlike the default visualize_fixes report, this renders a paired layout:
- one comparison case per (model family, specific_oid, iteration_id)
- docs and snippet variants shown side by side

Usage:
    python scripts/visualize_docs_vs_snippet_failures.py \
        --output evaluation/results/docs_fail_snippet_success/compare_report.html
"""

import argparse
import hashlib
import pickle
import sys
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.visualize_fixes import (
    compute_specific_oid,
    make_diff,
)
RESULTS_DIR = ROOT / "evaluation" / "results" / "docs_fail_snippet_success"
CASES_CSV = RESULTS_DIR / "all_models_cases.csv"
PROBLEMS_CSV = ROOT / "problems" / "benchmark_template_dedup_deterministic.csv"

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


def _text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v)


def _load_cases() -> pd.DataFrame:
    cases = pd.read_csv(CASES_CSV)
    cases["specific_oid"] = cases["specific_oid"].astype(str)
    cases["iteration_id"] = cases["iteration_id"].astype(int)
    return cases


def _load_raw(model_file: str) -> pd.DataFrame:
    path = ROOT / "llm_responses" / f"{model_file}.csv"
    df = pd.read_csv(path)
    if "specific_oid" not in df.columns:
        df = df.copy()
        df["specific_oid"] = df.apply(lambda r: compute_specific_oid(r.to_dict()), axis=1)
    df["specific_oid"] = df["specific_oid"].astype(str)
    df["iteration_id"] = df["iteration_id"].astype(int)
    for c in ["project_name", "filename", "llm_name", "summary", "detail", "fixed_block_content", "raw_llm_output"]:
        if c in df.columns:
            df[c] = df[c].fillna("")
    return df


def _load_outcomes(model_file: str) -> pd.DataFrame:
    path = ROOT / "llms_fixes_results" / f"{model_file}_repair_results.csv"
    df = pd.read_csv(path)
    df["specific_oid"] = df["specific_oid"].astype(str)
    df["iteration_id"] = df["iteration_id"].astype(int)
    return df


def _load_problems():
    problems = pd.read_csv(PROBLEMS_CSV)
    by_specific = problems.set_index("specific_oid", drop=False)
    by_oid = problems.set_index("oid", drop=False)
    return problems, by_specific, by_oid


def _select_problem_row(row, by_specific, by_oid):
    spec = row.get("specific_oid")
    if spec in by_specific.index:
        pr = by_specific.loc[spec]
        return pr.iloc[0] if isinstance(pr, pd.DataFrame) else pr
    oid = row.get("benchmark_oid") or row.get("oid_result") or row.get("oid")
    if oid in by_oid.index:
        pr = by_oid.loc[oid]
        return pr.iloc[0] if isinstance(pr, pd.DataFrame) else pr
    return None


def build_dataframe(ignore_whitespace: bool = False) -> pd.DataFrame:
    cases = _load_cases()
    _, by_specific, by_oid = _load_problems()

    rows = []
    for model_label, pair in MODEL_FILES.items():
        model_cases = cases[cases["model"] == model_label]
        if model_cases.empty:
            continue

        docs_raw = _load_raw(pair["docs"])
        snippet_raw = _load_raw(pair["snippet"])
        docs_out = _load_outcomes(pair["docs"])
        snippet_out = _load_outcomes(pair["snippet"])

        docs_raw = docs_raw.set_index(["specific_oid", "iteration_id"], drop=False)
        snippet_raw = snippet_raw.set_index(["specific_oid", "iteration_id"], drop=False)
        docs_out = docs_out.set_index(["specific_oid", "iteration_id"], drop=False)
        snippet_out = snippet_out.set_index(["specific_oid", "iteration_id"], drop=False)

        for _, case in model_cases.iterrows():
            key = (case["specific_oid"], int(case["iteration_id"]))
            docs_raw_row = docs_raw.loc[key]
            snippet_raw_row = snippet_raw.loc[key]
            docs_out_row = docs_out.loc[key]
            snippet_out_row = snippet_out.loc[key]

            for variant_name, raw_row, out_row in [
                ("docs", docs_raw_row, docs_out_row),
                ("snippet", snippet_raw_row, snippet_out_row),
            ]:
                original_problem = _select_problem_row(out_row.to_dict(), by_specific, by_oid)
                if original_problem is None:
                    original_content = ""
                    original_summary = ""
                    original_detail = ""
                else:
                    original_content = _text(original_problem.get("impacted_block_content", ""))
                    original_summary = _text(original_problem.get("summary", ""))
                    original_detail = _text(original_problem.get("detail", ""))

                modified_content = _text(raw_row.get("fixed_block_content", ""))
                llm_name = _text(raw_row.get("llm_name", ""))
                row = {
                    "project_name": _text(case.get("project_name")),
                    "filename": _text(case.get("filename")),
                    "line_start": case.get("line_start"),
                    "line_end": case.get("line_end"),
                    "severity": _text(case.get("severity")),
                    "summary": _text(case.get("summary")),
                    "detail": _text(case.get("detail")),
                    "provider_name": _text(case.get("provider_name")),
                    "block_type": _text(case.get("block_type")),
                    "problem_class": _text(case.get("problem_class")),
                    "problem_category": _text(case.get("problem_category")),
                    "metrics_depth": case.get("metrics_depth"),
                    "metrics_loc": case.get("metrics_loc"),
                    "metrics_nloc": case.get("metrics_nloc"),
                    "specific_oid": case["specific_oid"],
                    "iteration_id": int(case["iteration_id"]),
                    "oid": _text(out_row.get("oid", raw_row.get("oid", ""))),
                    "oid_result": _text(out_row.get("benchmark_oid", "")),
                    "llm_name": f"{llm_name} [{variant_name}]",
                    "fix_type": "Block Snippet",
                    "original_content": original_content,
                    "modified_content": modified_content,
                    "raw_llm_output": _text(raw_row.get("raw_llm_output", "")),
                    "original_problem_summary": original_summary,
                    "original_problem_detail": original_detail,
                    "is_fixed": out_row.get("is_fixed"),
                    "line_is_clean": out_row.get("line_is_clean"),
                    "line_specific_error_fixed": out_row.get("line_specific_error_fixed"),
                    "module_fix_introduced_errors": out_row.get("module_fix_introduced_errors", 0),
                    "module_original_errors_remaining": out_row.get("module_original_errors_remaining", 0),
                    "block_fix_introduced_errors": out_row.get("block_fix_introduced_errors", 0),
                    "block_original_errors_remaining": out_row.get("block_original_errors_remaining", 0),
                    "new_errors": [],
                    "explanation": "",
                    "variant": variant_name,
                    "model_family": model_label,
                }
                row["diff_same_exact"] = row["original_content"] == row["modified_content"]
                row["diff_same_ignore_ws"] = "".join(row["original_content"].split()) == "".join(row["modified_content"].split())
                row["diff"] = make_diff(
                    row["original_content"],
                    row["modified_content"],
                    ignore_whitespace=ignore_whitespace,
                )
                rows.append(row)

    return pd.DataFrame(rows)


def render_report(df: pd.DataFrame, output: Path):
    script_dir = Path(__file__).resolve().parent
    env = Environment(loader=FileSystemLoader(script_dir / "templates"))
    template = env.get_template("paired_compare_report.jinja")

    case_keys = [
        "model_family",
        "project_name",
        "filename",
        "line_start",
        "line_end",
        "severity",
        "summary",
        "specific_oid",
        "iteration_id",
    ]
    cases = []
    for key, group in df.groupby(case_keys, dropna=False):
        grouped = group.sort_values("variant")
        variants = {
            row["variant"]: row.to_dict()
            for _, row in grouped.iterrows()
        }
        docs = variants.get("docs")
        snippet = variants.get("snippet")
        base = docs or snippet
        if base is None:
            continue

        case_id = hashlib.md5(pickle.dumps(tuple(key))).hexdigest()
        pair_diff = ""
        if docs is not None and snippet is not None:
            pair_diff = make_diff(
                _text(docs.get("modified_content", "")),
                _text(snippet.get("modified_content", "")),
            )

        cases.append(
            {
                "case_id": case_id,
                "model_family": base["model_family"],
                "project_name": base["project_name"],
                "filename": base["filename"],
                "line_start": base["line_start"],
                "line_end": base["line_end"],
                "severity": base["severity"],
                "summary": base["summary"],
                "detail": base["detail"],
                "provider_name": base.get("provider_name", ""),
                "block_type": base.get("block_type", ""),
                "problem_class": base.get("problem_class", ""),
                "problem_category": base.get("problem_category", ""),
                "metrics_depth": base.get("metrics_depth"),
                "metrics_loc": base.get("metrics_loc"),
                "metrics_nloc": base.get("metrics_nloc"),
                "specific_oid": base["specific_oid"],
                "iteration_id": int(base["iteration_id"]),
                "original_problem_summary": base.get("original_problem_summary", ""),
                "original_problem_detail": base.get("original_problem_detail", ""),
                "docs": docs,
                "snippet": snippet,
                "pair_diff": pair_diff,
            }
        )

    cases.sort(
        key=lambda c: (
            str(c["model_family"]),
            str(c["project_name"]),
            str(c["filename"]),
            int(c["iteration_id"]),
            str(c["specific_oid"]),
        )
    )

    all_models = sorted(df["model_family"].dropna().astype(str).unique().tolist())
    all_iterations = sorted(df["iteration_id"].dropna().astype(int).unique().tolist())

    output.write_text(
        template.render(
            cases=cases,
            all_models=all_models,
            all_iterations=all_iterations,
        ),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Visualize docs-fail/snippet-succeed cases using visualize_fixes methodology")
    parser.add_argument(
        "--output",
        default=str(RESULTS_DIR / "compare_report.html"),
        help="Output HTML report path",
    )
    parser.add_argument(
        "--ignore-whitespace",
        action="store_true",
        help="Ignore all whitespace in diff rendering",
    )
    args = parser.parse_args()

    df = build_dataframe(ignore_whitespace=args.ignore_whitespace)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    render_report(df, output)
    print(f"[OK] Done! Report saved to: {output}")


if __name__ == "__main__":
    main()
