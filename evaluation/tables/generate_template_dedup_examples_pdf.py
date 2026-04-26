import argparse
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TEMPLATES = [
    ("resource helm_release", "Unsupported block type"),
    ("resource aws_s3_bucket", "Argument is deprecated"),
    ("resource kubernetes_namespace", "Deprecated Resource"),
]


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def compact(value: object, width: int = 120) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    text = " ".join(text.split())
    return textwrap.shorten(text, width=width, placeholder="...")


def truncate_block(block: object, max_lines: int = 18, max_width: int = 88) -> str:
    if pd.isna(block):
        return ""
    lines = str(block).replace("\r\n", "\n").replace("\r", "\n").splitlines()
    out = []
    for line in lines[:max_lines]:
        if len(line) > max_width:
            out.append(line[: max_width - 3] + "...")
        else:
            out.append(line)
    if len(lines) > max_lines:
        out.append(f"... ({len(lines) - max_lines} more lines)")
    return "\n".join(out)


def load_data(all_csv: Path, dedup_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "specific_oid",
        "project_name",
        "info_github",
        "filename",
        "line_start",
        "line_end",
        "block_type_full",
        "summary",
        "detail",
        "impacted_block_content",
        "metrics_attributes",
    ]
    all_df = pd.read_csv(all_csv, usecols=columns)
    dedup_df = pd.read_csv(dedup_csv, usecols=["specific_oid", "block_type_full", "summary", "detail"])

    for df in [all_df, dedup_df]:
        df["specific_oid"] = df["specific_oid"].astype(str)
        for key in ["block_type_full", "summary", "detail"]:
            df[key] = df[key].fillna("").astype(str)

    return all_df, dedup_df


def select_examples(all_df: pd.DataFrame, dedup_df: pd.DataFrame) -> list[dict]:
    keys = ["block_type_full", "summary", "detail"]
    dedup_keys = dedup_df[keys + ["specific_oid"]].rename(columns={"specific_oid": "retained_specific_oid"})

    template_counts = (
        all_df.groupby(keys, dropna=False)
        .agg(
            n_instances=("specific_oid", "nunique"),
            n_projects=("project_name", "nunique"),
            median_metrics_attributes=("metrics_attributes", "median"),
        )
        .reset_index()
        .merge(dedup_keys, on=keys, how="inner")
    )

    examples = []
    for block_type_full, summary in DEFAULT_TEMPLATES:
        matches = template_counts[
            (template_counts["block_type_full"] == block_type_full)
            & (template_counts["summary"] == summary)
            & (template_counts["n_instances"] > 1)
        ].sort_values(["n_instances", "n_projects"], ascending=False)
        if matches.empty:
            continue

        template = matches.iloc[0].to_dict()
        group = all_df[
            (all_df["block_type_full"] == template["block_type_full"])
            & (all_df["summary"] == template["summary"])
            & (all_df["detail"] == template["detail"])
        ].sort_values(["specific_oid", "project_name", "filename"])

        retained_rows = group[group["specific_oid"] == template["retained_specific_oid"]]
        retained = retained_rows.iloc[0] if not retained_rows.empty else group.iloc[0]
        duplicates = (
            group[group["specific_oid"] != retained["specific_oid"]]
            .drop_duplicates(subset=["specific_oid"])
            .head(3)
        )

        examples.append(
            {
                "template": template,
                "retained": retained,
                "duplicates": duplicates,
            }
        )

    if len(examples) < 3:
        selected_keys = {
            (
                ex["template"]["block_type_full"],
                ex["template"]["summary"],
                ex["template"]["detail"],
            )
            for ex in examples
        }
        fallback = template_counts[template_counts["n_instances"] > 1].sort_values(
            ["n_instances", "n_projects"], ascending=False
        )
        for _, template_row in fallback.iterrows():
            key = (template_row["block_type_full"], template_row["summary"], template_row["detail"])
            if key in selected_keys:
                continue
            group = all_df[
                (all_df["block_type_full"] == template_row["block_type_full"])
                & (all_df["summary"] == template_row["summary"])
                & (all_df["detail"] == template_row["detail"])
            ].sort_values(["specific_oid", "project_name", "filename"])
            retained_rows = group[group["specific_oid"] == template_row["retained_specific_oid"]]
            retained = retained_rows.iloc[0] if not retained_rows.empty else group.iloc[0]
            duplicates = (
                group[group["specific_oid"] != retained["specific_oid"]]
                .drop_duplicates(subset=["specific_oid"])
                .head(3)
            )
            examples.append({"template": template_row.to_dict(), "retained": retained, "duplicates": duplicates})
            if len(examples) >= 3:
                break

    return examples[:3]


def build_examples_table(examples: list[dict]) -> pd.DataFrame:
    rows = []
    for i, example in enumerate(examples, start=1):
        template = example["template"]
        retained = example["retained"]
        duplicates = example["duplicates"]
        rows.append(
            {
                "example_id": i,
                "block_type_full": template["block_type_full"],
                "summary": template["summary"],
                "detail": template["detail"],
                "template_size_before_dedup": int(template["n_instances"]),
                "projects_before_dedup": int(template["n_projects"]),
                "median_metrics_attributes": template["median_metrics_attributes"],
                "retained_specific_oid": retained["specific_oid"],
                "retained_project": retained["project_name"],
                "retained_github_url": retained["info_github"],
                "retained_filename": retained["filename"],
                "retained_lines": f"{int(retained['line_start'])}-{int(retained['line_end'])}",
                "removed_example_oids": ", ".join(duplicates["specific_oid"].astype(str).tolist()),
                "removed_example_projects": ", ".join(duplicates["project_name"].astype(str).tolist()),
                "removed_example_github_urls": " | ".join(duplicates["info_github"].fillna("").astype(str).tolist()),
            }
        )
    return pd.DataFrame(rows)


def add_wrapped_text(ax, x: float, y: float, text: str, width: int, **kwargs) -> float:
    lines = []
    for part in str(text).splitlines() or [""]:
        if not part:
            lines.append("")
        else:
            lines.extend(textwrap.wrap(part, width=width, replace_whitespace=False) or [""])
    ax.text(x, y, "\n".join(lines), **kwargs)
    return y - (0.035 * max(1, len(lines)))


def render_title_page(pdf: PdfPages, table: pd.DataFrame, all_df: pd.DataFrame, dedup_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")
    ax.text(0.05, 0.94, "Template-Level Deduplication Examples", fontsize=22, weight="bold", va="top")
    ax.text(
        0.05,
        0.88,
        "Replication package note: diagnostic templates are defined by block_type_full, summary, and detail.",
        fontsize=11,
        va="top",
    )

    body = (
        "To avoid over-representing repeated validation patterns, we apply a template-level "
        "deduplication step. A diagnostic template is the set of instances sharing the same "
        "block_type_full, summary, and detail. From each template, one representative instance "
        "is retained in the benchmark."
    )
    y = add_wrapped_text(ax, 0.05, 0.79, body, 115, fontsize=11, va="top")

    stats = (
        f"Source diagnostics: {len(all_df):,} rows. "
        f"Deduplicated benchmark: {len(dedup_df):,} rows. "
        f"Examples shown: {len(table)} duplicated templates."
    )
    y = add_wrapped_text(ax, 0.05, y - 0.03, stats, 115, fontsize=11, va="top")

    y -= 0.04
    ax.text(0.05, y, "Selected templates", fontsize=14, weight="bold", va="top")
    y -= 0.05
    for _, row in table.iterrows():
        text = (
            f"{row['example_id']}. {row['block_type_full']} | {row['summary']} | "
            f"{row['template_size_before_dedup']} original instances -> 1 retained"
        )
        y = add_wrapped_text(ax, 0.07, y, text, 105, fontsize=10, va="top")
        y -= 0.015

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def render_example_page(pdf: PdfPages, example: dict, example_id: int) -> None:
    template = example["template"]
    retained = example["retained"]
    duplicates = example["duplicates"]

    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")
    y = 0.95
    ax.text(0.05, y, f"Example {example_id}: Diagnostic Template", fontsize=18, weight="bold", va="top")
    y -= 0.06

    fields = [
        ("block_type_full", template["block_type_full"]),
        ("summary", template["summary"]),
        ("detail", compact(template["detail"], 200)),
        ("template size before dedup", f"{int(template['n_instances'])} instances across {int(template['n_projects'])} project(s)"),
        ("median number of attributes", f"{template['median_metrics_attributes']:.1f}"),
    ]
    for label, value in fields:
        y = add_wrapped_text(ax, 0.05, y, f"{label}: {value}", 118, fontsize=10.5, va="top")
        y -= 0.01

    y -= 0.02
    ax.text(0.05, y, "Retained representative", fontsize=13, weight="bold", va="top")
    y -= 0.04
    retained_meta = (
        f"specific_oid={retained['specific_oid']} | project={retained['project_name']} | "
        f"file={retained['filename']} | lines={int(retained['line_start'])}-{int(retained['line_end'])}"
    )
    y = add_wrapped_text(ax, 0.05, y, retained_meta, 118, fontsize=9.5, va="top")
    y = add_wrapped_text(ax, 0.05, y - 0.01, f"GitHub URL: {retained['info_github']}", 118, fontsize=8.6, va="top")
    y -= 0.02

    block = truncate_block(retained["impacted_block_content"])
    ax.text(
        0.05,
        y,
        block,
        fontsize=8.2,
        family="monospace",
        va="top",
        bbox={"facecolor": "#f3f3f3", "edgecolor": "#bbbbbb", "boxstyle": "round,pad=0.45"},
    )
    y -= min(0.38, 0.025 * (block.count("\n") + 1)) + 0.04

    ax.text(0.05, y, "Other instances removed by template deduplication", fontsize=13, weight="bold", va="top")
    y -= 0.045
    for dup_idx, (_, dup) in enumerate(duplicates.iterrows(), start=1):
        dup_text = (
            f"{dup_idx}. specific_oid={dup['specific_oid']} | project={dup['project_name']} | "
            f"file={dup['filename']} | lines={int(dup['line_start'])}-{int(dup['line_end'])}"
        )
        y = add_wrapped_text(ax, 0.06, y, dup_text, 112, fontsize=8.8, va="top")
        y = add_wrapped_text(ax, 0.06, y - 0.004, f"GitHub URL: {dup['info_github']}", 112, fontsize=7.8, va="top")
        dup_block = truncate_block(dup["impacted_block_content"], max_lines=7, max_width=95)
        ax.text(
            0.07,
            y - 0.006,
            dup_block,
            fontsize=6.8,
            family="monospace",
            va="top",
            bbox={"facecolor": "#f7f7f7", "edgecolor": "#d0d0d0", "boxstyle": "round,pad=0.35"},
        )
        y -= min(0.18, 0.018 * (dup_block.count("\n") + 1)) + 0.028
        if y < 0.08:
            break

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def write_markdown(table: pd.DataFrame, output_md: Path) -> None:
    lines = [
        "# Template-Level Deduplication Examples",
        "",
        "Diagnostic template key: `block_type_full`, `summary`, `detail`.",
        "",
        table.to_markdown(index=False),
        "",
    ]
    output_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a replication-package PDF with template-deduplication examples.")
    parser.add_argument("--all-csv", default="problems/ALL_LABELED_DIAGNOSTICS_merged.csv")
    parser.add_argument("--dedup-csv", default="problems/benchmark_template_dedup_deterministic.csv")
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/replication_package/template_deduplication_examples",
        help="Directory for PDF and companion tables.",
    )
    args = parser.parse_args()

    all_csv = resolve_path(args.all_csv)
    dedup_csv = resolve_path(args.dedup_csv)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_df, dedup_df = load_data(all_csv, dedup_csv)
    examples = select_examples(all_df, dedup_df)
    examples_table = build_examples_table(examples)

    output_pdf = output_dir / "template_deduplication_examples.pdf"
    output_csv = output_dir / "template_deduplication_examples.csv"
    output_md = output_dir / "template_deduplication_examples.md"

    examples_table.to_csv(output_csv, index=False)
    write_markdown(examples_table, output_md)

    with PdfPages(output_pdf) as pdf:
        render_title_page(pdf, examples_table, all_df, dedup_df)
        for idx, example in enumerate(examples, start=1):
            render_example_page(pdf, example, idx)

    print(f"[OK] wrote {output_pdf}")
    print(f"[OK] wrote {output_csv}")
    print(f"[OK] wrote {output_md}")


if __name__ == "__main__":
    main()
