import argparse
from pathlib import Path

import pandas as pd


MODEL_LABELS = {
    "CodeLlama_34b_Instruct_hf": "CodeLlama",
    "Codestral_22B_v0.1": "Codestral",
    "deepseek_coder_33b_instruct": "DeepSeek-Coder",
    "gpt_oss_20b": "GPT-OSS",
}


def split_variant(stem: str) -> tuple[str, str] | None:
    docs_suffix = "_docs_snippet_marked_code_only_xml_block_strict_pass_at_k_1_to_11"
    snippet_suffix = "_snippet_marked_code_only_xml_block_strict_pass_at_k_1_to_11"
    if stem.endswith(docs_suffix):
        return stem[: -len(docs_suffix)], "Docs"
    if stem.endswith(snippet_suffix):
        return stem[: -len(snippet_suffix)], "Snippet"
    return None


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}\\%"


def load_mean_row(path: Path) -> dict[str, float]:
    df = pd.read_csv(path)
    mean_row = df[df["specific_oid"].astype(str) == "MEAN"]
    if mean_row.empty:
        raise ValueError(f"Missing MEAN row in {path}")
    row = mean_row.iloc[0]
    return {
        "pass@1": float(row["pass@1"]),
        "pass@5": float(row["pass@5"]),
        "pass@10": float(row["pass@10"]),
    }


def build_rows(results_dir: Path) -> list[tuple[str, str, dict[str, float]]]:
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for path in sorted(results_dir.glob("*_block_strict_pass_at_k_1_to_11.csv")):
        parsed = split_variant(path.stem)
        if parsed is None:
            continue
        base_model, variant = parsed
        grouped.setdefault(base_model, {})[variant] = load_mean_row(path)

    rows: list[tuple[str, str, dict[str, float]]] = []
    for base_model in MODEL_LABELS:
        variants = grouped.get(base_model, {})
        if "Snippet" not in variants or "Docs" not in variants:
            missing = [name for name in ("Snippet", "Docs") if name not in variants]
            raise ValueError(f"Missing block-strict file(s) for {base_model}: {missing}")
        rows.append((MODEL_LABELS[base_model], "Snippet", variants["Snippet"]))
        rows.append((MODEL_LABELS[base_model], "Docs", variants["Docs"]))
    return rows


def render_table(rows: list[tuple[str, str, dict[str, float]]]) -> str:
    lines = [
        "% Requires: \\usepackage{booktabs}",
        "% Requires: \\usepackage{multirow}",
        "\\begin{table}[t]",
        "  \\centering",
        "  \\caption{Block-strict pass@k (\\%) for snippet-only and documentation-augmented prompting.}",
        "  \\label{tab:block-strict-passk-docs-vs-snippet}",
        "  \\begin{tabular}{llccc}",
        "    \\toprule",
        "    Model & Variant & pass@1 & pass@5 & pass@10 \\\\",
        "    \\midrule",
    ]

    for idx in range(0, len(rows), 2):
        model, variant_a, values_a = rows[idx]
        _, variant_b, values_b = rows[idx + 1]
        lines.append(
            f"    \\multirow{{2}}{{*}}{{{model}}} & {variant_a} & {format_pct(values_a['pass@1'])} & "
            f"{format_pct(values_a['pass@5'])} & {format_pct(values_a['pass@10'])} \\\\"
        )
        lines.append(
            f"     & {variant_b} & {format_pct(values_b['pass@1'])} & "
            f"{format_pct(values_b['pass@5'])} & {format_pct(values_b['pass@10'])} \\\\"
        )
        if idx + 2 < len(rows):
            lines.append("    \\midrule")

    lines.extend(
        [
            "    \\bottomrule",
            "  \\end{tabular}",
            "\\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Overleaf table for block-strict pass@k.")
    parser.add_argument("--results-dir", default="evaluation/results")
    parser.add_argument(
        "--output",
        default="evaluation/results/block_strict_passk_k1_k5_k10_overleaf.tex",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    results_dir = root / args.results_dir
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = build_rows(results_dir)
    output_path.write_text(render_table(rows), encoding="utf-8")
    print(f"[OK] wrote {output_path}")


if __name__ == "__main__":
    main()
