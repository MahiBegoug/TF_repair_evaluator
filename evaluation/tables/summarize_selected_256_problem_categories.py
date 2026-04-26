import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def build_category_summary(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    summary = (
        df.groupby("problem_category", dropna=False)
        .agg(
            n_instances=("specific_oid", "count"),
            median_metrics_attributes=("metrics_attributes", "median"),
            median_metrics_nested_block_count=("metrics_nested_block_count", "median"),
            median_metrics_loc=("metrics_loc", "median"),
            median_metrics_depth=("metrics_depth", "median"),
            mean_metrics_attributes=("metrics_attributes", "mean"),
            mean_metrics_nested_block_count=("metrics_nested_block_count", "mean"),
            mean_metrics_loc=("metrics_loc", "mean"),
            mean_metrics_depth=("metrics_depth", "mean"),
            min_metrics_attributes=("metrics_attributes", "min"),
            max_metrics_attributes=("metrics_attributes", "max"),
            min_metrics_nested_block_count=("metrics_nested_block_count", "min"),
            max_metrics_nested_block_count=("metrics_nested_block_count", "max"),
            min_metrics_loc=("metrics_loc", "min"),
            max_metrics_loc=("metrics_loc", "max"),
            min_metrics_depth=("metrics_depth", "min"),
            max_metrics_depth=("metrics_depth", "max"),
        )
        .reset_index()
        .sort_values(["n_instances", "problem_category"], ascending=[False, True])
    )
    summary["share_percent"] = (summary["n_instances"] / total) * 100.0
    return summary[
        [
            "problem_category",
            "n_instances",
            "share_percent",
            "median_metrics_attributes",
            "median_metrics_nested_block_count",
            "median_metrics_loc",
            "median_metrics_depth",
            "mean_metrics_attributes",
            "mean_metrics_nested_block_count",
            "mean_metrics_loc",
            "mean_metrics_depth",
            "min_metrics_attributes",
            "max_metrics_attributes",
            "min_metrics_nested_block_count",
            "max_metrics_nested_block_count",
            "min_metrics_loc",
            "max_metrics_loc",
            "min_metrics_depth",
            "max_metrics_depth",
        ]
    ]


def build_overall_summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "n_instances": len(df),
                "n_problem_categories": df["problem_category"].nunique(dropna=False),
                "median_metrics_attributes": df["metrics_attributes"].median(),
                "median_metrics_nested_block_count": df["metrics_nested_block_count"].median(),
                "median_metrics_loc": df["metrics_loc"].median(),
                "median_metrics_depth": df["metrics_depth"].median(),
                "mean_metrics_attributes": df["metrics_attributes"].mean(),
                "mean_metrics_nested_block_count": df["metrics_nested_block_count"].mean(),
                "mean_metrics_loc": df["metrics_loc"].mean(),
                "mean_metrics_depth": df["metrics_depth"].mean(),
                "min_metrics_attributes": df["metrics_attributes"].min(),
                "max_metrics_attributes": df["metrics_attributes"].max(),
                "min_metrics_nested_block_count": df["metrics_nested_block_count"].min(),
                "max_metrics_nested_block_count": df["metrics_nested_block_count"].max(),
                "min_metrics_loc": df["metrics_loc"].min(),
                "max_metrics_loc": df["metrics_loc"].max(),
                "min_metrics_depth": df["metrics_depth"].min(),
                "max_metrics_depth": df["metrics_depth"].max(),
            }
        ]
    )


def write_markdown(
    output_path: Path,
    input_csv: Path,
    overall: pd.DataFrame,
    category_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Selected 256 Benchmark Problem Category Summary",
        "",
        f"Input dataset: `{input_csv}`",
        "",
        "## Overall",
        "",
        overall.to_markdown(index=False),
        "",
        "## By Problem Category",
        "",
        category_summary.to_markdown(index=False),
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize the selected 256 benchmark instances by problem_category and metrics_attributes."
    )
    parser.add_argument(
        "--input-csv",
        default="problems/benchmark_template_dedup_deterministic.csv",
        help="Selected benchmark CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/results/replication_package/selected_256_problem_category_summary",
        help="Directory for generated summary files.",
    )
    args = parser.parse_args()

    input_csv = resolve_path(args.input_csv)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    required_columns = [
        "specific_oid",
        "problem_category",
        "metrics_attributes",
        "metrics_nested_block_count",
        "metrics_loc",
        "metrics_depth",
    ]
    df = pd.read_csv(input_csv, usecols=required_columns)
    df["specific_oid"] = df["specific_oid"].astype(str)
    df["problem_category"] = df["problem_category"].fillna("Uncategorized").astype(str)
    df["metrics_attributes"] = pd.to_numeric(df["metrics_attributes"], errors="coerce")
    df["metrics_nested_block_count"] = pd.to_numeric(df["metrics_nested_block_count"], errors="coerce")
    df["metrics_loc"] = pd.to_numeric(df["metrics_loc"], errors="coerce")
    df["metrics_depth"] = pd.to_numeric(df["metrics_depth"], errors="coerce")

    overall = build_overall_summary(df)
    category_summary = build_category_summary(df)

    overall_path = output_dir / "selected_256_overall_summary.csv"
    category_path = output_dir / "selected_256_problem_category_summary.csv"
    markdown_path = output_dir / "selected_256_problem_category_summary.md"

    overall.to_csv(overall_path, index=False)
    category_summary.to_csv(category_path, index=False)
    write_markdown(markdown_path, input_csv, overall, category_summary)

    print(f"[OK] wrote {overall_path}")
    print(f"[OK] wrote {category_path}")
    print(f"[OK] wrote {markdown_path}")
    print()
    print("Overall:")
    print(overall.to_string(index=False))
    print()
    print("By problem_category:")
    print(category_summary.to_string(index=False))


if __name__ == "__main__":
    main()
