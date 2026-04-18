import html

import pandas as pd

from repair_analyzer.renderers import (
    _bar_chart,
    _horizontal_bar_chart_svg,
    _metric_card,
    _normalized_scope_by_iteration_svg,
    _radar_chart_svg,
    _stacked_area_chart_svg,
    _table_html,
)
from repair_analyzer.summaries import (
    _fixed_message_distribution_rows,
    _introduced_message_distribution_rows,
    _summary_resolution_rows,
)
from repair_analyzer.utils import _format_pct


def _render_html_report(
    report_title: str,
    iteration_summary_df: pd.DataFrame,
    fixed_types_overall_df: pd.DataFrame,
    introduced_scope_by_iteration_df: pd.DataFrame,
    introduced_types_overall_df: pd.DataFrame,
    introduced_scope_summary_df: pd.DataFrame,
    introduced_audit_df: pd.DataFrame,
    transition_df: pd.DataFrame,
    lifecycle_df: pd.DataFrame,
) -> str:
    total_attempts = int(iteration_summary_df["repairs_attempted"].sum()) if not iteration_summary_df.empty else 0
    total_fixed = int(iteration_summary_df["fixed_repairs"].sum()) if not iteration_summary_df.empty else 0
    total_strict_fixed = int(iteration_summary_df["strict_fixed_repairs"].sum()) if not iteration_summary_df.empty else 0
    total_introduced = int(iteration_summary_df["introduced_diagnostics"].sum()) if not iteration_summary_df.empty else 0

    fixed_rate_rows = iteration_summary_df[["iteration_id", "fix_rate"]].rename(columns={"iteration_id": "label", "fix_rate": "value"}).to_dict("records")
    introduced_rows = iteration_summary_df[["iteration_id", "introduced_diagnostics"]].rename(columns={"iteration_id": "label", "introduced_diagnostics": "value"}).to_dict("records")
    top_fixed_pct_rows = _fixed_message_distribution_rows(fixed_types_overall_df, limit=10)
    top_intro_pct_rows = _introduced_message_distribution_rows(introduced_types_overall_df, limit=10)
    summary_resolution_rows = _summary_resolution_rows(fixed_types_overall_df, limit=8)
    scope_rows = introduced_scope_summary_df[["scope_granularity", "introduced_diagnostics"]].rename(columns={"scope_granularity": "label", "introduced_diagnostics": "value"}).to_dict("records") if not introduced_scope_summary_df.empty else []
    audit_table = _table_html(
        introduced_audit_df[
            [
                "repairs_attempted",
                "repairs_with_outcomes",
                "repairs_missing_outcomes",
                "repairs_with_matching_introduced_counts",
                "repairs_with_mismatching_introduced_counts",
                "introduced_count_match_rate",
                "introduced_total_gap_raw_minus_classified",
                "strict_success_disagreement_repairs",
                "strict_success_agreement_rate",
            ]
        ]
        if not introduced_audit_df.empty
        else introduced_audit_df,
        formatters={
            "introduced_count_match_rate": _format_pct,
            "strict_success_agreement_rate": _format_pct,
        },
    )

    solved_unresolved_svg = _stacked_area_chart_svg(iteration_summary_df)
    scope_by_iteration_svg = _normalized_scope_by_iteration_svg(introduced_scope_by_iteration_df)
    top_fixed_svg = _horizontal_bar_chart_svg(
        "Most Often Strictly Fixed Problem Types (%)",
        top_fixed_pct_rows,
        "label",
        "value",
        "#1d4ed8",
        value_formatter=lambda value: f"{value * 100:.1f}%",
        x_axis_max=1.0,
    )
    top_intro_svg = _horizontal_bar_chart_svg(
        "Most Common Introduced Diagnostic Types (%)",
        top_intro_pct_rows,
        "label",
        "value",
        "#d97706",
        value_formatter=lambda value: f"{value * 100:.1f}%",
        x_axis_max=1.0,
    )
    summary_radar_svg = _radar_chart_svg(
        "Summary-Level Strict Resolution Profile (%)",
        summary_resolution_rows,
        "#2563eb",
    )

    metrics_html = "".join(
        [
            _metric_card("Repair Attempts", str(total_attempts), "All evaluated iterations"),
            _metric_card("Fixed Attempts", str(total_fixed), "Original diagnostic resolved"),
            _metric_card("Strict Fixes", str(total_strict_fixed), "Resolved with no introduced diagnostics"),
            _metric_card("Introduced Diagnostics", str(total_introduced), "New diagnostics created by repairs"),
        ]
    )

    charts_html = "".join(
        [
            '<section class="chart-card chart-card-wide"><h3>Figure 1. Solved and Unresolved Problems Across Iterations</h3>'
            f'{solved_unresolved_svg or "<p class=\"empty-state\">No data available.</p>"}'
            "</section>",
            _bar_chart("Figure 2. Fix Rate by Iteration", fixed_rate_rows, "label", "value", "#0f766e", _format_pct),
            _bar_chart("Figure 3. Introduced Diagnostics by Iteration", introduced_rows, "label", "value", "#b91c1c", lambda value: str(int(round(value)))),
            '<section class="chart-card chart-card-wide"><h3>Figure 4. Introduced Diagnostics by Scope Across Iterations (%)</h3>'
            f'{scope_by_iteration_svg or "<p class=\"empty-state\">No data available.</p>"}'
            "</section>",
            '<section class="chart-card chart-card-wide"><h3>Figure 5. Most Often Strictly Fixed Problem Types (%)</h3>'
            f'{top_fixed_svg or "<p class=\"empty-state\">No data available.</p>"}'
            "</section>",
            '<section class="chart-card chart-card-wide"><h3>Figure 6. Most Common Introduced Diagnostic Types (%)</h3>'
            f'{top_intro_svg or "<p class=\"empty-state\">No data available.</p>"}'
            "</section>",
            '<section class="chart-card chart-card-wide"><h3>Figure 7. Summary-Level Strict Resolution Profile (%)</h3>'
            f'{summary_radar_svg or "<p class=\"empty-state\">No data available.</p>"}'
            "</section>",
            _bar_chart("Figure 8. Introduced Diagnostics by Scope", scope_rows, "label", "value", "#7c3aed", lambda value: str(int(round(value)))),
        ]
    )

    iteration_table = _table_html(
        iteration_summary_df[
            [
                "iteration_id",
                "repairs_attempted",
                "fixed_repairs",
                "fix_rate",
                "strict_fixed_repairs",
                "strict_fix_rate",
                "repairs_with_introduced_diagnostics",
                "introduced_diagnostics",
                "new_problems_fixed",
                "cumulative_fix_coverage",
            ]
        ],
        formatters={"fix_rate": _format_pct, "strict_fix_rate": _format_pct, "cumulative_fix_coverage": _format_pct},
    )
    fixed_table = _table_html(
        fixed_types_overall_df[
            [
                "problem_type_label",
                "repairs_attempted",
                "fixed_repairs",
                "fix_rate",
                "strict_fixed_repairs",
                "strict_fix_rate",
            ]
        ],
        formatters={"fix_rate": _format_pct, "strict_fix_rate": _format_pct},
    )
    introduced_table = _table_html(
        introduced_types_overall_df[
            [
                "introduced_type_label",
                "introduced_diagnostics",
                "affected_repairs",
                "same_block_diagnostics",
                "same_file_other_block_diagnostics",
                "same_module_other_file_diagnostics",
                "outside_original_module_diagnostics",
                "truly_new_diagnostics",
                "cross_iteration_repeats",
            ]
        ]
        if not introduced_types_overall_df.empty
        else introduced_types_overall_df,
    )
    transition_table = _table_html(
        transition_df[
            [
                "iteration_id",
                "problem_type_label",
                "introduced_type_label",
                "scope_granularity",
                "transition_count",
                "affected_repairs",
            ]
        ]
        if not transition_df.empty
        else transition_df
    )
    lifecycle_table = _table_html(
        lifecycle_df[
            [
                "problem_type_label",
                "attempts",
                "fixes",
                "strict_fixes",
                "introduced_diagnostics",
                "first_fixed_iteration",
                "first_strict_fixed_iteration",
            ]
        ],
        limit=20,
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(report_title)}</title>
  <style>
    :root {{
      --bg: #f7f4ee;
      --panel: #fffdf9;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d6d3d1;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #fde68a 0, transparent 28%),
        radial-gradient(circle at bottom right, #bfdbfe 0, transparent 26%),
        var(--bg);
    }}
    .page {{ max-width: 1400px; margin: 0 auto; padding: 32px 20px 48px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(15,118,110,0.96), rgba(30,41,59,0.94));
      color: white;
      border-radius: 22px;
      padding: 28px;
      box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
    }}
    .hero h1 {{ margin: 0 0 8px; font-size: clamp(28px, 4vw, 42px); line-height: 1.05; }}
    .hero p {{ margin: 0; max-width: 780px; color: rgba(255,255,255,0.9); font-size: 16px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 22px; }}
    .metric-card {{
      background: rgba(255,255,255,0.14);
      border: 1px solid rgba(255,255,255,0.18);
      border-radius: 16px;
      padding: 16px 18px;
    }}
    .metric-title {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255,255,255,0.78); }}
    .metric-value {{ font-size: 34px; font-weight: 700; margin-top: 6px; }}
    .metric-subtitle {{ margin-top: 4px; color: rgba(255,255,255,0.82); font-size: 14px; }}
    .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 18px; }}
    .chart-card, .table-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }}
    .chart-card-wide {{ grid-column: 1 / -1; }}
    .chart-card h3, .table-card h3 {{ margin: 0 0 14px; font-size: 18px; }}
    .chart-row {{ display: grid; grid-template-columns: minmax(100px, 1.1fr) minmax(120px, 2.4fr) 84px; gap: 10px; align-items: center; margin-bottom: 10px; }}
    .chart-label {{ font-size: 14px; line-height: 1.3; }}
    .chart-track {{ height: 12px; background: #ece8df; border-radius: 999px; overflow: hidden; }}
    .chart-bar {{ height: 100%; border-radius: 999px; }}
    .chart-value {{ text-align: right; font-size: 13px; font-weight: 600; color: var(--muted); }}
    .tables {{ display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 16px; }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-family: "Segoe UI", sans-serif;
      font-size: 13px;
    }}
    .data-table th, .data-table td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #e7e5e4; vertical-align: top; }}
    .data-table th {{ background: #fafaf9; font-weight: 600; }}
    .empty-state {{ color: var(--muted); font-style: italic; margin: 0; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>{html.escape(report_title)}</h1>
      <p>Iteration-aware analysis of what TFRepair fixed, what it introduced, and how those behaviors changed across repeated attempts.</p>
      <div class="metrics">{metrics_html}</div>
    </section>
    <section class="charts">{charts_html}</section>
    <section class="tables">
      <div class="table-card"><h3>Iteration Summary</h3>{iteration_table}</div>
      <div class="table-card"><h3>Fixed Problem Types</h3>{fixed_table}</div>
      <div class="table-card"><h3>Introduced Diagnostic Types</h3>{introduced_table}</div>
      <div class="table-card"><h3>Introduced Error Audit</h3>{audit_table}</div>
      <div class="table-card"><h3>Problem Type to Introduced Type Transitions</h3>{transition_table}</div>
      <div class="table-card"><h3>Problem Lifecycle Across Iterations</h3>{lifecycle_table}</div>
    </section>
  </div>
</body>
</html>
"""
