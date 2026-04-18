from collections.abc import Callable
import html
import math
import textwrap

import pandas as pd

from repair_analyzer.constants import SCOPE_LEVELS
from repair_analyzer.utils import _iteration_sort_key, _safe_text


def _table_html(df: pd.DataFrame, formatters: dict[str, Callable] | None = None, limit: int = 15) -> str:
    if df.empty:
        return '<p class="empty-state">No data available.</p>'
    preview_df = df.head(limit).copy()
    if formatters:
        for column, formatter in formatters.items():
            if column in preview_df.columns:
                preview_df[column] = preview_df[column].map(formatter)
    return preview_df.to_html(index=False, escape=True, classes="data-table")


def _metric_card(title: str, value: str, subtitle: str) -> str:
    return (
        '<div class="metric-card">'
        f'<div class="metric-title">{html.escape(title)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-subtitle">{html.escape(subtitle)}</div>'
        "</div>"
    )


def _bar_chart(title: str, rows: list[dict], label_key: str, value_key: str, color: str, value_formatter) -> str:
    if not rows:
        return (
            '<section class="chart-card">'
            f"<h3>{html.escape(title)}</h3>"
            '<p class="empty-state">No data available.</p>'
            "</section>"
        )

    max_value = max(float(row[value_key]) for row in rows) or 1.0
    chart_rows = []
    for row in rows:
        label = _safe_text(row[label_key], default="-")
        value = float(row[value_key])
        width = max(4.0, (value / max_value) * 100.0) if value > 0 else 0.0
        chart_rows.append(
            '<div class="chart-row">'
            f'<div class="chart-label">{html.escape(label)}</div>'
            '<div class="chart-track">'
            f'<div class="chart-bar" style="width: {width:.2f}%; background: {color};"></div>'
            "</div>"
            f'<div class="chart-value">{html.escape(value_formatter(value))}</div>'
            "</div>"
        )

    return '<section class="chart-card">' f"<h3>{html.escape(title)}</h3>" + "".join(chart_rows) + "</section>"


def _stacked_area_chart_svg(iteration_summary_df: pd.DataFrame) -> str:
    if iteration_summary_df.empty:
        return ""

    chart_df = iteration_summary_df.sort_values("iteration_order").copy()
    total_tasks = int(chart_df["unique_problems"].max()) if "unique_problems" in chart_df.columns else int(chart_df["repairs_attempted"].max())
    if total_tasks <= 0:
        return ""

    width = 760
    height = 360
    margin_left = 68
    margin_right = 20
    margin_top = 24
    margin_bottom = 42
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    labels = chart_df["iteration_id"].astype(str).tolist()
    solved = chart_df["cumulative_problems_fixed"].astype(float).tolist()

    if len(labels) == 1:
        x_positions = [margin_left + plot_width / 2]
    else:
        step = plot_width / (len(labels) - 1)
        x_positions = [margin_left + idx * step for idx in range(len(labels))]

    def y_scale(value: float) -> float:
        return margin_top + plot_height - (value / total_tasks) * plot_height

    green_points = [(x, y_scale(value)) for x, value in zip(x_positions, solved)]
    green_polygon = [(margin_left, margin_top + plot_height)] + green_points + [(margin_left + plot_width, margin_top + plot_height)]
    green_points_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in green_polygon)
    boundary_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in green_points)
    y_ticks = sorted({0, total_tasks // 4, total_tasks // 2, (3 * total_tasks) // 4, total_tasks})
    y_tick_lines = []
    for tick in y_ticks:
        y = y_scale(tick)
        y_tick_lines.append(
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" y2="{y:.2f}" stroke="#e7e5e4" stroke-width="1"/>'
            f'<text x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{tick}</text>'
        )
    x_tick_labels = []
    for x, label in zip(x_positions, labels):
        x_tick_labels.append(
            f'<line x1="{x:.2f}" y1="{margin_top + plot_height}" x2="{x:.2f}" y2="{margin_top + plot_height + 6}" stroke="#6b7280" stroke-width="1"/>'
            f'<text x="{x:.2f}" y="{margin_top + plot_height + 22}" text-anchor="middle" font-size="12" fill="#6b7280">{html.escape(label)}</text>'
        )
    unresolved_label_y = y_scale(solved[-1]) / 2 + margin_top / 2
    solved_label_y = y_scale(solved[-1]) + (margin_top + plot_height - y_scale(solved[-1])) / 2
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Solved and unresolved problems by iteration">
  <rect x="{margin_left}" y="{margin_top}" width="{plot_width}" height="{plot_height}" fill="#fda4af"/>
  {''.join(y_tick_lines)}
  <polygon points="{green_points_text}" fill="#9bd7c2" opacity="0.98"/>
  <polyline points="{boundary_points}" fill="none" stroke="#1f2937" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  <line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#374151" stroke-width="1.5"/>
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#374151" stroke-width="1.5"/>
  {''.join(x_tick_labels)}
  <text x="{width / 2:.2f}" y="{height - 6}" text-anchor="middle" font-size="13" fill="#374151">Iteration</text>
  <text x="18" y="{height / 2:.2f}" text-anchor="middle" font-size="13" fill="#374151" transform="rotate(-90 18 {height / 2:.2f})">Number of Problems</text>
  <text x="{width * 0.58:.2f}" y="{unresolved_label_y:.2f}" text-anchor="middle" font-size="18" fill="#111827">Unresolved</text>
  <text x="{width * 0.56:.2f}" y="{solved_label_y:.2f}" text-anchor="middle" font-size="18" fill="#111827">Solved</text>
</svg>
"""


def _horizontal_bar_chart_svg(
    title: str,
    rows: list[dict],
    label_key: str,
    value_key: str,
    bar_color: str,
    width: int = 760,
    height_per_row: int = 36,
    value_formatter: Callable | None = None,
    x_axis_max: float | None = None,
) -> str:
    if not rows:
        return ""

    sorted_rows = sorted(rows, key=lambda row: float(row[value_key]), reverse=True)
    frame_x = 12
    frame_y = 12
    frame_width = width - (frame_x * 2)
    plot_left = frame_x + 8
    plot_right = frame_x + frame_width - 8
    margin_top = frame_y + 10
    chart_height = max(210, margin_top + 10 + height_per_row * len(rows))
    frame_height = chart_height - frame_y - 12
    plot_width = plot_right - plot_left
    max_value = x_axis_max if x_axis_max is not None else max(float(row[value_key]) for row in sorted_rows) or 1.0
    formatter = value_formatter or (lambda value: str(int(round(value))))

    y_rows = []
    for idx, row in enumerate(sorted_rows):
        y = margin_top + idx * height_per_row + 8
        label = _safe_text(row[label_key], default="-")
        value = float(row[value_key])
        value_text = html.escape(formatter(value))
        bar_width = (value / max_value) * plot_width
        text_y = y + 9
        bar_end = plot_left + bar_width
        label_width_estimate = max(len(label) * 6.3, 36.0)
        value_width_estimate = max(len(value_text) * 6.0, 24.0)
        value_inside = bar_width >= value_width_estimate + 14.0
        label_inside = bar_width >= label_width_estimate + value_width_estimate + 26.0
        label_x = plot_left + 8 if label_inside else min(bar_end + 8, plot_right - 4)
        value_x = max(bar_end - 8, plot_left + 8) if value_inside else min(bar_end + 8, plot_right - 4)
        if not label_inside and not value_inside:
            label_x = min(bar_end + value_width_estimate + 14.0, plot_right - 4)
        y_rows.append(
            f'<rect x="{plot_left}" y="{y:.2f}" width="{bar_width:.2f}" height="18" rx="0" fill="{bar_color}"/>'
            f'<text x="{label_x:.2f}" y="{text_y:.2f}" text-anchor="start" dominant-baseline="middle" font-size="12" font-style="italic" fill="{"#ffffff" if label_inside else "#111827"}">{html.escape(label)}</text>'
            f'<text x="{value_x:.2f}" y="{text_y:.2f}" text-anchor="{"end" if value_inside else "start"}" dominant-baseline="middle" font-size="12" fill="#111827">{value_text}</text>'
        )

    return f"""
<svg viewBox="0 0 {width} {chart_height}" role="img" aria-label="{html.escape(title)}">
  <rect x="{frame_x}" y="{frame_y}" width="{frame_width}" height="{frame_height}" fill="white" stroke="#6b7280" stroke-width="1"/>
  {''.join(y_rows)}
</svg>
"""


def _normalized_scope_by_iteration_svg(scope_by_iteration_df: pd.DataFrame) -> str:
    if scope_by_iteration_df.empty:
        return ""

    chart_df = scope_by_iteration_df.copy()
    iterations = sorted(chart_df["iteration_id"].astype(str).unique(), key=_iteration_sort_key)
    pivot_df = (
        chart_df.pivot_table(
            index="iteration_id",
            columns="scope_granularity",
            values="introduced_diagnostics",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(iterations)
        .fillna(0)
    )
    for scope_name in SCOPE_LEVELS:
        if scope_name not in pivot_df.columns:
            pivot_df[scope_name] = 0
    percent_df = pivot_df[SCOPE_LEVELS].div(pivot_df.sum(axis=1).replace(0, 1), axis=0) * 100.0

    width = 760
    height = 380
    margin_left = 68
    margin_right = 20
    margin_top = 24
    margin_bottom = 48
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    step = plot_width / max(len(iterations), 1)
    bar_width = max(18.0, step * 0.68)
    colors = {
        "same_block": "#0f766e",
        "same_file_other_block": "#eab308",
        "same_module_other_file": "#f97316",
        "outside_original_module": "#b91c1c",
    }
    labels = {
        "same_block": "Same block",
        "same_file_other_block": "Same file, other block",
        "same_module_other_file": "Same module, other file",
        "outside_original_module": "Outside module",
    }

    def y_scale(value: float) -> float:
        return margin_top + plot_height - (value / 100.0) * plot_height

    tick_svg = []
    for tick in [0, 25, 50, 75, 100]:
        y = y_scale(tick)
        tick_svg.append(
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" y2="{y:.2f}" stroke="#e7e5e4" stroke-width="1"/>'
            f'<text x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{tick}%</text>'
        )

    bars_svg = []
    for idx, iteration in enumerate(iterations):
        x = margin_left + idx * step + (step - bar_width) / 2
        running = 0.0
        for scope_name in SCOPE_LEVELS:
            value = float(percent_df.loc[iteration, scope_name])
            if value <= 0:
                continue
            y_top = y_scale(running + value)
            y_bottom = y_scale(running)
            bars_svg.append(
                f'<rect x="{x:.2f}" y="{y_top:.2f}" width="{bar_width:.2f}" height="{(y_bottom - y_top):.2f}" fill="{colors[scope_name]}"/>'
            )
            running += value
        bars_svg.append(
            f'<text x="{x + bar_width / 2:.2f}" y="{margin_top + plot_height + 22:.2f}" text-anchor="middle" font-size="12" fill="#6b7280">{html.escape(str(iteration))}</text>'
        )

    legend_svg = []
    for idx, scope_name in enumerate(SCOPE_LEVELS):
        x = margin_left + idx * 165
        legend_svg.append(
            f'<rect x="{x}" y="{height - 24}" width="12" height="12" fill="{colors[scope_name]}"/>'
            f'<text x="{x + 18}" y="{height - 14:.2f}" font-size="12" fill="#374151">{labels[scope_name]}</text>'
        )

    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Normalized introduced diagnostics by scope and iteration">
  {''.join(tick_svg)}
  <line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#374151" stroke-width="1.5"/>
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#374151" stroke-width="1.5"/>
  {''.join(bars_svg)}
  <text x="{width / 2:.2f}" y="{height - 26}" text-anchor="middle" font-size="13" fill="#374151">Iteration</text>
  <text x="18" y="{height / 2:.2f}" text-anchor="middle" font-size="13" fill="#374151" transform="rotate(-90 18 {height / 2:.2f})">Share of Introduced Diagnostics (%)</text>
  {''.join(legend_svg)}
</svg>
"""


def _wrap_label_lines(label: str, width: int = 18, max_lines: int = 2) -> list[str]:
    wrapped = textwrap.wrap(_safe_text(label, default="-"), width=width) or ["-"]
    if len(wrapped) <= max_lines:
        return wrapped
    head = wrapped[: max_lines - 1]
    tail = " ".join(wrapped[max_lines - 1 :])
    return head + [textwrap.shorten(tail, width=width, placeholder="...")]


def _radar_chart_svg(title: str, rows: list[dict], color: str, width: int = 760, height: int = 520) -> str:
    if not rows:
        return ""

    cx = width / 2
    cy = height / 2 + 6
    radius = min(width, height) * 0.28
    label_radius = radius + 42
    angles = [(-math.pi / 2) + (2 * math.pi * idx / len(rows)) for idx in range(len(rows))]

    def point(angle: float, scale: float) -> tuple[float, float]:
        return cx + math.cos(angle) * radius * scale, cy + math.sin(angle) * radius * scale

    grid_svg = []
    for level in [0.25, 0.5, 0.75, 1.0]:
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (point(angle, level) for angle in angles))
        grid_svg.append(f'<polygon points="{points}" fill="none" stroke="#d6d3d1" stroke-width="1"/>')
        grid_svg.append(f'<text x="{cx + 8:.2f}" y="{cy - radius * level - 4:.2f}" font-size="11" fill="#6b7280">{int(level * 100)}%</text>')
    for angle in angles:
        x, y = point(angle, 1.0)
        grid_svg.append(f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="#d6d3d1" stroke-width="1"/>')

    polygon_points = [point(angle, float(row["value"])) for angle, row in zip(angles, rows)]
    polygon_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in polygon_points)
    outline_text = polygon_text + f" {polygon_points[0][0]:.2f},{polygon_points[0][1]:.2f}"

    labels_svg = []
    for angle, row in zip(angles, rows):
        label_x = cx + math.cos(angle) * label_radius
        label_y = cy + math.sin(angle) * label_radius
        lines = _wrap_label_lines(row["label"], width=18, max_lines=2)
        anchor = "middle" if abs(math.cos(angle)) < 0.2 else ("start" if math.cos(angle) > 0 else "end")
        tspans = []
        for idx, line in enumerate(lines):
            tspans.append(f'<tspan x="{label_x:.2f}" dy="{"0" if idx == 0 else "1.15em"}">{html.escape(line)}</tspan>')
        labels_svg.append(
            f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{anchor}" font-size="12" fill="#111827">{"".join(tspans)}</text>'
        )

    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <rect x="12" y="12" width="{width - 24}" height="{height - 24}" fill="white" stroke="#6b7280" stroke-width="1"/>
  <text x="{width / 2:.2f}" y="36" text-anchor="middle" font-size="16" fill="#111827">{html.escape(title)}</text>
  {''.join(grid_svg)}
  <polygon points="{polygon_text}" fill="{color}" opacity="0.22"/>
  <polyline points="{outline_text}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>
  {''.join(labels_svg)}
</svg>
"""


def _save_solved_unsolved_pdf(iteration_summary_df: pd.DataFrame, output_path: str) -> None:
    if iteration_summary_df.empty:
        return
    import matplotlib.pyplot as plt

    chart_df = iteration_summary_df.sort_values("iteration_order").copy()
    iterations = chart_df["iteration_id"].astype(str).tolist()
    solved = chart_df["cumulative_problems_fixed"].astype(float).tolist()
    total_tasks = int(chart_df["unique_problems"].max()) if "unique_problems" in chart_df.columns else int(chart_df["repairs_attempted"].max())

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.fill_between(iterations, 0, solved, color="#9bd7c2", alpha=0.95)
    ax.fill_between(iterations, solved, [total_tasks] * len(iterations), color="#fda4af", alpha=0.95)
    ax.plot(iterations, solved, color="#1f2937", linewidth=2.2)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Number of Problems")
    ax.set_title("Solved and Unresolved Problems Across Iterations")
    ax.text(len(iterations) * 0.55, total_tasks * 0.78, "Unresolved", fontsize=12)
    ax.text(len(iterations) * 0.52, total_tasks * 0.35, "Solved", fontsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def _save_scope_by_iteration_pdf(scope_by_iteration_df: pd.DataFrame, output_path: str) -> None:
    if scope_by_iteration_df.empty:
        return
    import matplotlib.pyplot as plt

    iterations = sorted(scope_by_iteration_df["iteration_id"].astype(str).unique(), key=_iteration_sort_key)
    pivot_df = (
        scope_by_iteration_df.pivot_table(
            index="iteration_id",
            columns="scope_granularity",
            values="introduced_diagnostics",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(iterations)
        .fillna(0)
    )
    for scope_name in SCOPE_LEVELS:
        if scope_name not in pivot_df.columns:
            pivot_df[scope_name] = 0
    percent_df = pivot_df[SCOPE_LEVELS].div(pivot_df.sum(axis=1).replace(0, 1), axis=0) * 100.0
    colors = {
        "same_block": "#0f766e",
        "same_file_other_block": "#eab308",
        "same_module_other_file": "#f97316",
        "outside_original_module": "#b91c1c",
    }
    labels = {
        "same_block": "Same block",
        "same_file_other_block": "Same file, other block",
        "same_module_other_file": "Same module, other file",
        "outside_original_module": "Outside module",
    }

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    bottom = [0.0] * len(percent_df.index)
    for scope_name in SCOPE_LEVELS:
        values = percent_df[scope_name].tolist()
        ax.bar(percent_df.index.astype(str), values, bottom=bottom, color=colors[scope_name], label=labels[scope_name])
        bottom = [b + v for b, v in zip(bottom, values)]
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of Introduced Diagnostics (%)")
    ax.set_xlabel("Iteration")
    ax.set_title("Introduced Diagnostics by Scope Across Iterations (%)")
    ax.legend(frameon=False, ncol=2, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.14), borderaxespad=0.0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.subplots_adjust(bottom=0.25)
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def _save_horizontal_percentage_pdf(title: str, rows: list[dict], output_path: str, color: str) -> None:
    if not rows:
        return
    import matplotlib.pyplot as plt

    labels = [row["label"] for row in sorted(rows, key=lambda row: float(row["value"]), reverse=True)][::-1]
    values = [float(row["value"]) * 100.0 for row in sorted(rows, key=lambda row: float(row["value"]), reverse=True)][::-1]
    axis_max = 100.0
    fig_height = max(4.5, 0.42 * len(rows) + 1.2)
    fig, ax = plt.subplots(figsize=(8.6, fig_height))
    bars = ax.barh(list(range(len(labels))), values, color=color)
    ax.set_xlim(0, axis_max)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_xlabel("")
    ax.set_title("")
    ax.tick_params(axis="x", length=0)
    for label, value, bar in zip(labels, values, bars):
        y_center = bar.get_y() + bar.get_height() / 2
        value_text = f"{value:.1f}%"
        label_width_estimate = axis_max * (0.012 * len(label) + 0.04)
        value_width_estimate = axis_max * (0.013 * len(value_text) + 0.02)
        value_inside = value >= value_width_estimate + axis_max * 0.02
        label_inside = value >= label_width_estimate + value_width_estimate + axis_max * 0.04
        value_x = max(value - axis_max * 0.012, 0.18) if value_inside else min(value + axis_max * 0.02, axis_max - 1.5)
        label_x = 0.35 if label_inside else min(value + axis_max * 0.02, axis_max - 1.5)
        if not label_inside and not value_inside:
            label_x = min(value + value_width_estimate + axis_max * 0.04, axis_max - 1.5)
        ax.text(label_x, y_center, label, va="center", ha="left", fontsize=9, fontstyle="italic", color="#ffffff" if label_inside else "#111827")
        ax.text(value_x, y_center, value_text, va="center", ha="right" if value_inside else "left", fontsize=9, color="#111827")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
        spine.set_color("#6b7280")
    ax.grid(False)
    ax.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def _save_paired_distribution_figure(
    left_title: str,
    left_rows: list[dict],
    right_title: str,
    right_rows: list[dict],
    output_path: str,
    output_format: str,
) -> None:
    if not left_rows and not right_rows:
        return
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.6))
    panels = [
        (axes[0], left_title, sorted(left_rows, key=lambda row: float(row["value"]), reverse=True)[:10], "#486581"),
        (axes[1], right_title, sorted(right_rows, key=lambda row: float(row["value"]), reverse=True)[:10], "#486581"),
    ]
    for ax, title, rows, color in panels:
        if not rows:
            ax.axis("off")
            continue
        labels = [row["label"] for row in rows][::-1]
        values = [float(row["value"]) * 100.0 for row in rows][::-1]
        axis_max = 100.0
        bars = ax.barh(list(range(len(labels))), values, color=color, edgecolor="white", linewidth=0.6)
        ax.set_yticks([])
        ax.set_xlim(0, axis_max)
        ax.set_xticks([])
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", length=0)
        ax.set_title(title, fontsize=13)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.8)
            spine.set_color("#6b7280")
        for label, bar, value in zip(labels, bars, values):
            y_center = bar.get_y() + bar.get_height() / 2
            value_text = f"{value:.1f}%"
            label_width_estimate = axis_max * (0.012 * len(label) + 0.04)
            value_width_estimate = axis_max * (0.013 * len(value_text) + 0.02)
            value_inside = value >= value_width_estimate + axis_max * 0.02
            label_inside = value >= label_width_estimate + value_width_estimate + axis_max * 0.04
            value_x = max(value - axis_max * 0.012, 0.18) if value_inside else min(value + axis_max * 0.02, axis_max - 1.5)
            label_x = 0.35 if label_inside else min(value + axis_max * 0.02, axis_max - 1.5)
            if not label_inside and not value_inside:
                label_x = min(value + value_width_estimate + axis_max * 0.04, axis_max - 1.5)
            ax.text(label_x, y_center, label, va="center", ha="left", fontsize=9, fontstyle="italic", color="#ffffff" if label_inside else "#374151")
            ax.text(value_x, y_center, value_text, va="center", ha="right" if value_inside else "left", fontsize=9, color="#374151")
        ax.grid(False)
        ax.set_facecolor("white")
    fig.tight_layout(w_pad=2.5)
    fig.savefig(output_path, format=output_format, bbox_inches="tight")
    plt.close(fig)


def _save_radar_pdf(title: str, rows: list[dict], output_path: str, color: str) -> None:
    if not rows:
        return
    import matplotlib.pyplot as plt

    labels = ["\n".join(_wrap_label_lines(row["label"], width=18, max_lines=2)) for row in rows]
    values = [float(row["value"]) * 100.0 for row in rows]
    angles = [2 * math.pi * idx / len(rows) for idx in range(len(rows))]
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(8.2, 6.6), subplot_kw={"projection": "polar"})
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_rticks([25, 50, 75, 100])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=8, color="#6b7280")
    ax.set_rlabel_position(0)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.plot(angles_closed, values_closed, color=color, linewidth=2.4)
    ax.fill(angles_closed, values_closed, color=color, alpha=0.22)
    ax.grid(color="#d6d3d1")
    ax.spines["polar"].set_color("#6b7280")
    ax.spines["polar"].set_linewidth(0.8)
    ax.set_title(title, y=1.10, fontsize=13)
    fig.tight_layout()
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)
