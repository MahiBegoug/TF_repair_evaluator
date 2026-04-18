import os
from pathlib import Path

from repair_analyzer.loader import load_repair_analysis_data
from repair_analyzer.renderers import (
    _horizontal_bar_chart_svg,
    _normalized_scope_by_iteration_svg,
    _radar_chart_svg,
    _save_horizontal_percentage_pdf,
    _save_paired_distribution_figure,
    _save_radar_pdf,
    _save_scope_by_iteration_pdf,
    _save_solved_unsolved_pdf,
    _stacked_area_chart_svg,
)
from repair_analyzer.report import _render_html_report
from repair_analyzer.summaries import (
    _fixed_message_distribution_rows,
    _introduced_message_distribution_rows,
    _summary_resolution_overall_df,
    _summary_resolution_rows,
    build_fixed_types_by_iteration,
    build_fixed_types_overall,
    build_introduced_error_audit,
    build_introduced_error_mismatch_detail,
    build_introduced_diagnostics_detail,
    build_introduced_scope_by_iteration,
    build_introduced_scope_summary,
    build_introduced_types_by_iteration,
    build_introduced_types_overall,
    build_iteration_summary,
    build_problem_lifecycle,
    build_transition_summary,
)
from repair_analyzer.utils import _pick_writable_path


def generate_repair_analysis_artifacts(
    fixes_csv: str,
    outcomes_csv: str,
    diagnostics_csv: str | None = None,
    analysis_dir: str | None = None,
    problems_csv: str | None = None,
    report_title: str | None = None,
):
    attempts_df, diagnostics_df, _ = load_repair_analysis_data(
        fixes_csv=fixes_csv,
        outcomes_csv=outcomes_csv,
        diagnostics_csv=diagnostics_csv,
        problems_csv=problems_csv,
    )
    iteration_summary_df = build_iteration_summary(attempts_df)
    lifecycle_df = build_problem_lifecycle(attempts_df)
    fixed_types_by_iteration_df = build_fixed_types_by_iteration(attempts_df)
    fixed_types_overall_df = build_fixed_types_overall(attempts_df)
    introduced_types_by_iteration_df = build_introduced_types_by_iteration(attempts_df, diagnostics_df)
    introduced_types_overall_df = build_introduced_types_overall(attempts_df, diagnostics_df)
    introduced_scope_summary_df = build_introduced_scope_summary(diagnostics_df)
    introduced_scope_by_iteration_df = build_introduced_scope_by_iteration(diagnostics_df)
    introduced_detail_df = build_introduced_diagnostics_detail(diagnostics_df)
    introduced_audit_df = build_introduced_error_audit(attempts_df)
    introduced_audit_mismatch_df = build_introduced_error_mismatch_detail(attempts_df)
    transition_df = build_transition_summary(attempts_df, diagnostics_df)
    summary_resolution_df = _summary_resolution_overall_df(fixed_types_overall_df)

    if analysis_dir is None:
        outcome_stem = Path(outcomes_csv).with_suffix("").name
        analysis_dir = os.path.join("repair_analyzer", "generated", f"{outcome_stem}_analysis")

    report_title = report_title or f"TFRepair Analysis for {Path(outcomes_csv).stem}"
    csv_dir = os.path.join(analysis_dir, "csv")
    reports_dir = os.path.join(analysis_dir, "reports")
    figures_svg_dir = os.path.join(analysis_dir, "figures", "svg")
    figures_pdf_dir = os.path.join(analysis_dir, "figures", "pdf")
    for directory in [csv_dir, reports_dir, figures_svg_dir, figures_pdf_dir]:
        os.makedirs(directory, exist_ok=True)

    outputs = {
        "attempt_level_csv": os.path.join(csv_dir, "attempt_level_analysis.csv"),
        "iteration_summary_csv": os.path.join(csv_dir, "iteration_summary.csv"),
        "problem_lifecycle_csv": os.path.join(csv_dir, "problem_lifecycle.csv"),
        "fixed_types_by_iteration_csv": os.path.join(csv_dir, "fixed_types_by_iteration.csv"),
        "fixed_types_overall_csv": os.path.join(csv_dir, "fixed_types_overall.csv"),
        "summary_resolution_overall_csv": os.path.join(csv_dir, "summary_resolution_overall.csv"),
        "introduced_types_by_iteration_csv": os.path.join(csv_dir, "introduced_types_by_iteration.csv"),
        "introduced_types_overall_csv": os.path.join(csv_dir, "introduced_types_overall.csv"),
        "introduced_scope_summary_csv": os.path.join(csv_dir, "introduced_scope_summary.csv"),
        "introduced_scope_by_iteration_csv": os.path.join(csv_dir, "introduced_scope_by_iteration.csv"),
        "introduced_diagnostics_detailed_csv": os.path.join(csv_dir, "introduced_diagnostics_detailed.csv"),
        "introduced_error_audit_csv": os.path.join(csv_dir, "introduced_error_audit.csv"),
        "introduced_error_audit_mismatches_csv": os.path.join(csv_dir, "introduced_error_audit_mismatches.csv"),
        "transition_summary_csv": os.path.join(csv_dir, "type_transitions.csv"),
        "solved_unsolved_figure_svg": os.path.join(figures_svg_dir, "solved_unsolved_by_iteration.svg"),
        "introduced_scope_figure_svg": os.path.join(figures_svg_dir, "introduced_scope_by_iteration.svg"),
        "top_fixed_types_figure_svg": os.path.join(figures_svg_dir, "top_fixed_types.svg"),
        "top_introduced_types_figure_svg": os.path.join(figures_svg_dir, "top_introduced_types.svg"),
        "summary_resolution_radar_figure_svg": os.path.join(figures_svg_dir, "summary_resolution_radar.svg"),
        "paired_distribution_figure_svg": os.path.join(figures_svg_dir, "strictly_fixed_vs_introduced.svg"),
        "solved_unsolved_figure_pdf": os.path.join(figures_pdf_dir, "solved_unsolved_by_iteration.pdf"),
        "introduced_scope_figure_pdf": os.path.join(figures_pdf_dir, "introduced_scope_by_iteration.pdf"),
        "top_fixed_types_figure_pdf": os.path.join(figures_pdf_dir, "top_fixed_types.pdf"),
        "top_introduced_types_figure_pdf": os.path.join(figures_pdf_dir, "top_introduced_types.pdf"),
        "summary_resolution_radar_figure_pdf": os.path.join(figures_pdf_dir, "summary_resolution_radar.pdf"),
        "paired_distribution_figure_pdf": os.path.join(figures_pdf_dir, "strictly_fixed_vs_introduced.pdf"),
        "html_report": os.path.join(reports_dir, "repair_analysis_report.html"),
    }

    for key in [
        "solved_unsolved_figure_svg",
        "introduced_scope_figure_svg",
        "top_fixed_types_figure_svg",
        "top_introduced_types_figure_svg",
        "summary_resolution_radar_figure_svg",
        "paired_distribution_figure_svg",
        "solved_unsolved_figure_pdf",
        "introduced_scope_figure_pdf",
        "top_fixed_types_figure_pdf",
        "top_introduced_types_figure_pdf",
        "summary_resolution_radar_figure_pdf",
        "paired_distribution_figure_pdf",
        "html_report",
    ]:
        outputs[key] = _pick_writable_path(outputs[key])

    attempts_df.to_csv(outputs["attempt_level_csv"], index=False)
    iteration_summary_df.to_csv(outputs["iteration_summary_csv"], index=False)
    lifecycle_df.to_csv(outputs["problem_lifecycle_csv"], index=False)
    fixed_types_by_iteration_df.to_csv(outputs["fixed_types_by_iteration_csv"], index=False)
    fixed_types_overall_df.to_csv(outputs["fixed_types_overall_csv"], index=False)
    summary_resolution_df.to_csv(outputs["summary_resolution_overall_csv"], index=False)
    introduced_types_by_iteration_df.to_csv(outputs["introduced_types_by_iteration_csv"], index=False)
    introduced_types_overall_df.to_csv(outputs["introduced_types_overall_csv"], index=False)
    introduced_scope_summary_df.to_csv(outputs["introduced_scope_summary_csv"], index=False)
    introduced_scope_by_iteration_df.to_csv(outputs["introduced_scope_by_iteration_csv"], index=False)
    introduced_detail_df.to_csv(outputs["introduced_diagnostics_detailed_csv"], index=False)
    introduced_audit_df.to_csv(outputs["introduced_error_audit_csv"], index=False)
    introduced_audit_mismatch_df.to_csv(outputs["introduced_error_audit_mismatches_csv"], index=False)
    transition_df.to_csv(outputs["transition_summary_csv"], index=False)

    top_fixed_pct_rows = _fixed_message_distribution_rows(fixed_types_overall_df, limit=10)
    top_intro_pct_rows = _introduced_message_distribution_rows(introduced_types_overall_df, limit=10)
    summary_resolution_rows = _summary_resolution_rows(fixed_types_overall_df, limit=8)

    with open(outputs["solved_unsolved_figure_svg"], "w", encoding="utf-8") as handle:
        handle.write(_stacked_area_chart_svg(iteration_summary_df))
    with open(outputs["introduced_scope_figure_svg"], "w", encoding="utf-8") as handle:
        handle.write(_normalized_scope_by_iteration_svg(introduced_scope_by_iteration_df))
    with open(outputs["top_fixed_types_figure_svg"], "w", encoding="utf-8") as handle:
        handle.write(_horizontal_bar_chart_svg("Most Often Strictly Fixed Problem Types (%)", top_fixed_pct_rows, "label", "value", "#1d4ed8", value_formatter=lambda value: f"{value * 100:.1f}%", x_axis_max=1.0))
    with open(outputs["top_introduced_types_figure_svg"], "w", encoding="utf-8") as handle:
        handle.write(_horizontal_bar_chart_svg("Most Common Introduced Diagnostic Types (%)", top_intro_pct_rows, "label", "value", "#d97706", value_formatter=lambda value: f"{value * 100:.1f}%", x_axis_max=1.0))
    with open(outputs["summary_resolution_radar_figure_svg"], "w", encoding="utf-8") as handle:
        handle.write(_radar_chart_svg("Summary-Level Strict Resolution Profile (%)", summary_resolution_rows, "#2563eb"))

    _save_paired_distribution_figure("Strictly Fixed Problem Types (%)", top_fixed_pct_rows, "Newly Introduced Diagnostic Types (%)", top_intro_pct_rows, outputs["paired_distribution_figure_svg"], "svg")
    _save_solved_unsolved_pdf(iteration_summary_df, outputs["solved_unsolved_figure_pdf"])
    _save_scope_by_iteration_pdf(introduced_scope_by_iteration_df, outputs["introduced_scope_figure_pdf"])
    _save_horizontal_percentage_pdf("Most Often Strictly Fixed Problem Types (%)", top_fixed_pct_rows, outputs["top_fixed_types_figure_pdf"], "#1d4ed8")
    _save_horizontal_percentage_pdf("Most Common Introduced Diagnostic Types (%)", top_intro_pct_rows, outputs["top_introduced_types_figure_pdf"], "#d97706")
    _save_radar_pdf("Summary-Level Strict Resolution Profile (%)", summary_resolution_rows, outputs["summary_resolution_radar_figure_pdf"], "#2563eb")
    _save_paired_distribution_figure("Strictly Fixed Problem Types (%)", top_fixed_pct_rows, "Newly Introduced Diagnostic Types (%)", top_intro_pct_rows, outputs["paired_distribution_figure_pdf"], "pdf")

    html_report = _render_html_report(
        report_title=report_title,
        iteration_summary_df=iteration_summary_df,
        fixed_types_overall_df=fixed_types_overall_df,
        introduced_scope_by_iteration_df=introduced_scope_by_iteration_df,
        introduced_types_overall_df=introduced_types_overall_df,
        introduced_scope_summary_df=introduced_scope_summary_df,
        introduced_audit_df=introduced_audit_df,
        transition_df=transition_df,
        lifecycle_df=lifecycle_df,
    )
    with open(outputs["html_report"], "w", encoding="utf-8") as handle:
        handle.write(html_report)
    return outputs
