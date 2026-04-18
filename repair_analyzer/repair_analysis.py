import argparse

from repair_analyzer.loader import load_repair_analysis_data
from repair_analyzer.pipeline import generate_repair_analysis_artifacts
from repair_analyzer.summaries import (
    build_fixed_types_overall,
    build_introduced_error_audit,
    build_introduced_types_overall,
    build_iteration_summary,
    build_problem_lifecycle,
)

__all__ = [
    "build_fixed_types_overall",
    "build_introduced_error_audit",
    "build_introduced_types_overall",
    "build_iteration_summary",
    "build_problem_lifecycle",
    "generate_repair_analysis_artifacts",
    "load_repair_analysis_data",
    "main",
]


def main():
    parser = argparse.ArgumentParser(description="Generate iteration-aware repair analysis artifacts")
    parser.add_argument("--fixes-csv", required=True, help="LLM fixes/input CSV used for repair evaluation")
    parser.add_argument("--outcomes-csv", required=True, help="Repair outcomes CSV produced by evaluation")
    parser.add_argument("--diagnostics-csv", help="Diagnostics CSV produced by evaluation")
    parser.add_argument("--analysis-dir", help="Output directory for CSV summaries and HTML report")
    parser.add_argument("--problems-csv", help="Optional problems CSV for richer block metadata")
    parser.add_argument("--report-title", help="Optional HTML report title")
    args = parser.parse_args()

    outputs = generate_repair_analysis_artifacts(
        fixes_csv=args.fixes_csv,
        outcomes_csv=args.outcomes_csv,
        diagnostics_csv=args.diagnostics_csv,
        analysis_dir=args.analysis_dir,
        problems_csv=args.problems_csv,
        report_title=args.report_title,
    )

    print("Generated repair analysis artifacts:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
