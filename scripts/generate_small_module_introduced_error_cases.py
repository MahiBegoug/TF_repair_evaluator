from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "manual_inspection" / "introduced_errors_small_modules"

SELECTED_CASES = [
    "e064de81f5a8",  # ministryofjustice__opg-digideps
    "b6afb35dd38f",  # databrickslabs__overwatch
    "ca09187e68fc",  # dirien__quick-bites
    "743c58e0c299",  # weaveworks__build-tools
]

MODEL_FILES = [
    "CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml",
    "CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml",
    "Codestral_22B_v0.1_docs_snippet_marked_code_only_xml",
    "Codestral_22B_v0.1_snippet_marked_code_only_xml",
    "deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml",
    "deepseek_coder_33b_instruct_snippet_marked_code_only_xml",
    "gpt_oss_20b_docs_snippet_marked_code_only_xml",
    "gpt_oss_20b_snippet_marked_code_only_xml",
]


def fenced(text: str, lang: str = "") -> str:
    text = "" if text is None else str(text)
    return f"```{lang}\n{text.rstrip()}\n```\n"


def short_name(model_file: str) -> str:
    name = model_file.replace("_snippet_marked_code_only_xml", "")
    name = name.replace("_docs", " [docs]")
    return name


def render_table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "_none_\n"
    subset = df[cols].copy()
    return subset.to_markdown(index=False) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    problems = pd.read_csv(ROOT / "problems" / "benchmark_template_dedup_deterministic.csv")
    project_sizes = problems.groupby("project_name").size().rename("project_problem_count")
    problems = problems.merge(project_sizes, on="project_name", how="left")

    raw_map = {
        model: pd.read_csv(ROOT / "llm_responses" / f"{model}.csv")
        for model in MODEL_FILES
    }
    repair_map = {
        model: pd.read_csv(ROOT / "llms_fixes_results" / f"{model}_repair_results.csv")
        for model in MODEL_FILES
    }
    diag_map = {
        model: pd.read_csv(ROOT / "llms_fixes_results" / f"{model}_new_diagnostics_after_validation.csv")
        for model in MODEL_FILES
    }
    for mapping in (raw_map, repair_map, diag_map):
        for _, df in mapping.items():
            if "specific_oid" in df.columns:
                df["specific_oid"] = df["specific_oid"].astype(str)
            if "original_problem_specific_oid" in df.columns:
                df["original_problem_specific_oid"] = df["original_problem_specific_oid"].astype(str)
            if "iteration_id" in df.columns:
                df["iteration_id"] = df["iteration_id"].astype(int)

    index_rows = []
    for i, specific_oid in enumerate(SELECTED_CASES, start=1):
        p_row = problems[problems["specific_oid"].astype(str) == specific_oid]
        if p_row.empty:
            continue
        p_row = p_row.iloc[0]

        project = str(p_row["project_name"])
        baseline = problems[problems["project_name"] == project].copy()

        run_sections = []
        run_summaries = []
        for model in MODEL_FILES:
            repair = repair_map[model]
            repair_case = repair[
                (repair["specific_oid"] == specific_oid)
                & (repair["module_fix_introduced_errors"].fillna(0).astype(int) > 0)
            ].copy()
            if repair_case.empty:
                continue

            repair_case = repair_case.sort_values(["module_fix_introduced_errors", "iteration_id"])
            chosen = repair_case.iloc[0]
            iteration = int(chosen["iteration_id"])

            raw = raw_map[model]
            raw_case = raw[
                (raw["specific_oid"] == specific_oid)
                & (raw["iteration_id"] == iteration)
            ]
            raw_case = raw_case.iloc[0] if not raw_case.empty else None

            diags = diag_map[model]
            diag_case = diags[
                (diags["original_problem_specific_oid"] == specific_oid)
                & (diags["iteration_id"] == iteration)
            ].copy()
            introduced = diag_case[diag_case["introduced_in_this_iteration"].fillna(False).astype(bool)].copy()
            remaining = diag_case[diag_case["is_original_error"].fillna(False).astype(bool)].copy()

            run_summaries.append(
                {
                    "model": short_name(model),
                    "iteration": iteration,
                    "module_fix_introduced_errors": int(chosen["module_fix_introduced_errors"]),
                    "block_fix_introduced_errors": int(chosen["block_fix_introduced_errors"]),
                    "line_specific_error_fixed": bool(chosen["line_specific_error_fixed"]),
                    "line_is_clean": bool(chosen["line_is_clean"]) if pd.notna(chosen["line_is_clean"]) else None,
                }
            )

            section = [
                f"## {short_name(model)}",
                "",
                f"- iteration: `{iteration}`",
                f"- module_fix_introduced_errors: `{int(chosen['module_fix_introduced_errors'])}`",
                f"- block_fix_introduced_errors: `{int(chosen['block_fix_introduced_errors'])}`",
                f"- line_specific_error_fixed: `{bool(chosen['line_specific_error_fixed'])}`",
                f"- line_is_clean: `{chosen['line_is_clean']}`",
                "",
                "### Fixed block content",
                fenced(raw_case.get("fixed_block_content", "") if raw_case is not None else "", "hcl"),
                "### Raw LLM output",
                fenced(raw_case.get("raw_llm_output", "") if raw_case is not None else ""),
                "### Introduced diagnostics after validation",
                render_table(
                    introduced,
                    ["severity", "summary", "detail", "filename", "line_start", "block_type", "block_identifiers"],
                ),
                "### Remaining baseline diagnostics after validation",
                render_table(
                    remaining,
                    ["severity", "summary", "detail", "filename", "line_start", "block_type", "block_identifiers"],
                ),
            ]
            run_sections.append("\n".join(section))

        filename = f"{i:02d}_{specific_oid}_{project}.md".replace("__", "_")
        out_path = OUT_DIR / filename
        index_rows.append(
            {
                "specific_oid": specific_oid,
                "project_name": project,
                "filename": str(p_row["filename"]),
                "project_problem_count": int(p_row["project_problem_count"]),
                "output_file": filename,
            }
        )

        doc = [
            f"# Manual Inspection Case {i}: `{specific_oid}`",
            "",
            "## Why this case",
            "",
            "- selected because the project has a very small benchmark baseline, which makes before/after inspection manageable",
            "- selected only from cases where `module_fix_introduced_errors > 0`",
            "",
            "## Benchmark problem",
            "",
            f"- project: `{project}`",
            f"- file: `{p_row['filename']}`",
            f"- summary: `{p_row['summary']}`",
            f"- detail: `{p_row['detail']}`",
            f"- provider: `{p_row['provider_name']}`",
            f"- block_type: `{p_row['block_type']}`",
            f"- file_loc: `{int(p_row['file_loc'])}`",
            f"- metrics_depth: `{int(p_row['metrics_depth'])}`",
            f"- project_problem_count in benchmark: `{int(p_row['project_problem_count'])}`",
            "",
            "## Baseline diagnostics for this project in the benchmark",
            "",
            render_table(
                baseline,
                ["specific_oid", "filename", "summary", "detail", "line_start", "block_type", "block_identifiers"],
            ),
            "## Runs selected for inspection",
            "",
            render_table(pd.DataFrame(run_summaries), ["model", "iteration", "module_fix_introduced_errors", "block_fix_introduced_errors", "line_specific_error_fixed", "line_is_clean"]),
            "\n".join(run_sections),
        ]
        out_path.write_text("\n".join(doc), encoding="utf-8")

    readme = [
        "# Introduced Error Manual Inspection",
        "",
        "These files are intended for manual validation of `introduced_in_this_iteration` and `module_fix_introduced_errors`.",
        "",
        "Selection criteria:",
        "- only cases with `module_fix_introduced_errors > 0`",
        "- preference for projects with very small benchmark baselines",
        "- one markdown file per selected `specific_oid`",
        "",
        "Each file contains:",
        "- the benchmark baseline diagnostics for the project",
        "- one representative introduced-error run per model/variant when available",
        "- the candidate patch",
        "- the raw LLM output",
        "- the introduced diagnostics after validation",
        "- the remaining baseline diagnostics after validation",
        "",
        "## Index",
        "",
        render_table(pd.DataFrame(index_rows), ["specific_oid", "project_name", "filename", "project_problem_count", "output_file"]),
    ]
    (OUT_DIR / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"[OK] Wrote inspection bundle to {OUT_DIR}")


if __name__ == "__main__":
    main()
