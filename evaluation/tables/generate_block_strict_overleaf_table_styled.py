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
        return stem[: -len(docs_suffix)], "Local Context + Schema"
    if stem.endswith(snippet_suffix):
        return stem[: -len(snippet_suffix)], "Local Context"
    return None


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}\\%"


def format_pct_cell(value: float, *, bold: bool = False) -> str:
    text = format_pct(value)
    if bold:
        return f"\\textbf{{{text}}}"
    return text


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


def format_p_value(value: float) -> str:
    if value < 0.001:
        return "$<.001$"
    return f"{value:.3f}"


def format_effect(value: float) -> str:
    return f"{value:.2f}"


def significance_stars(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return ""


def effect_code(value: float) -> str:
    a = abs(value)
    if a < 0.10:
        return "N"
    if a < 0.30:
        return "S"
    if a < 0.50:
        return "M"
    return "L"


def is_tied(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(a - b) <= tol


def direction_symbol(current: float, baseline: float, tol: float = 1e-12) -> str:
    if current > baseline + tol:
        return "\\textcolor{green!60!black}{$\\uparrow$}"
    if current < baseline - tol:
        return "\\textcolor{red!70!black}{$\\downarrow$}"
    return ""


def format_schema_cell(value: float, baseline: float, p_value: float, effect: float, *, bold: bool = False) -> str:
    value_text = format_pct(value)
    direction = direction_symbol(value, baseline)
    stars = significance_stars(p_value)
    annotated = f"{value_text}{direction} ({effect_code(effect)}){stars}"
    if bold:
        return f"\\textbf{{{annotated}}}"
    return annotated


def load_pairwise_stats(stats_path: Path) -> dict[str, dict[int, dict[str, float]]]:
    df = pd.read_csv(stats_path)
    stats = {}
    for _, row in df[df["k"].isin([1, 5, 10])].iterrows():
        model_name = str(row["model_a"])
        base_name = model_name.replace("_docs_snippet_marked_code_only_xml", "")
        stats.setdefault(base_name, {})[int(row["k"])] = {
            "p": float(row["wilcoxon_p_value"]),
            "r": float(row["rank_biserial"]),
        }
    return stats


def build_rows(results_dir: Path, stats_by_model: dict[str, dict[int, dict[str, float]]]) -> list[tuple[str, str, dict[str, float], dict[int, dict[str, float]]]]:
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for path in sorted(results_dir.glob("*_block_strict_pass_at_k_1_to_11.csv")):
        parsed = split_variant(path.stem)
        if parsed is None:
            continue
        base_model, variant = parsed
        grouped.setdefault(base_model, {})[variant] = load_mean_row(path)

    rows: list[tuple[str, str, dict[str, float], dict[int, dict[str, float]]]] = []
    for base_model in MODEL_LABELS:
        variants = grouped.get(base_model, {})
        if "Local Context" not in variants or "Local Context + Schema" not in variants:
            missing = [name for name in ("Local Context", "Local Context + Schema") if name not in variants]
            raise ValueError(f"Missing block-strict file(s) for {base_model}: {missing}")
        if base_model not in stats_by_model:
            raise ValueError(f"Missing pairwise block-strict stats for {base_model}")
        rows.append((MODEL_LABELS[base_model], "Local Context", variants["Local Context"], stats_by_model[base_model]))
        rows.append((MODEL_LABELS[base_model], "Local Context + Schema", variants["Local Context + Schema"], stats_by_model[base_model]))
    return rows


def render_table(rows: list[tuple[str, str, dict[str, float], dict[int, dict[str, float]]]], caption: str, label: str) -> str:
    lines = [
        "% Requires: \\usepackage{booktabs}",
        "% Requires: \\usepackage[table]{xcolor}",
        "% Requires: \\usepackage{multirow}",
        "% Optional: \\usepackage{array}",
        "\\begin{table}[H]",
        "\\centering",
        "\\fontsize{5}{7}\\selectfont",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\renewcommand{\\arraystretch}{0.95}",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\begin{tabular}{@{} p{1.2 cm} p{2cm} l l l @{}}",
        "\\toprule",
        "\\rowcolor{black}",
        "\\textcolor{white}{\\textbf{Model}} &",
        "\\textcolor{white}{\\textbf{Prompt Style}} &",
        "\\textcolor{white}{\\textbf{pass@1}} &",
        "\\textcolor{white}{\\textbf{pass@5}} &",
        "\\textcolor{white}{\\textbf{pass@10}} \\\\",
        "\\midrule",
    ]

    for idx in range(0, len(rows), 2):
        model, variant_a, values_a, stats = rows[idx]
        _, variant_b, values_b, _ = rows[idx + 1]
        best_1 = max(values_a["pass@1"], values_b["pass@1"])
        best_5 = max(values_a["pass@5"], values_b["pass@5"])
        best_10 = max(values_a["pass@10"], values_b["pass@10"])
        lines.append(
            f"\\multirow{{2}}{{*}}{{\\textbf{{{model}}}}} & {variant_a} & "
            f"{format_pct_cell(values_a['pass@1'], bold=is_tied(values_a['pass@1'], best_1))} & "
            f"{format_pct_cell(values_a['pass@5'], bold=is_tied(values_a['pass@5'], best_5))} & "
            f"{format_pct_cell(values_a['pass@10'], bold=is_tied(values_a['pass@10'], best_10))} \\\\"
        )
        lines.append("\\cmidrule(lr){2-5}")
        lines.append(
            f" & {variant_b} & "
            f"{format_schema_cell(values_b['pass@1'], values_a['pass@1'], stats[1]['p'], stats[1]['r'], bold=is_tied(values_b['pass@1'], best_1))} & "
            f"{format_schema_cell(values_b['pass@5'], values_a['pass@5'], stats[5]['p'], stats[5]['r'], bold=is_tied(values_b['pass@5'], best_5))} & "
            f"{format_schema_cell(values_b['pass@10'], values_a['pass@10'], stats[10]['p'], stats[10]['r'], bold=is_tied(values_b['pass@10'], best_10))} \\\\"
        )
        if idx + 2 < len(rows):
            lines.append("\\midrule")

    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\vspace{2pt}",
            "\\begin{minipage}{\\linewidth}",
            "\\fontsize{5}{6}\\selectfont",
            "\\textit{\\textbf{Note.}} $\\uparrow$ and $\\downarrow$ indicate improvement and degradation with respect to the Local Context baseline.\\\\",
            "Effect sizes are reported using Cliff's Delta (N=negligible, S=small, M=medium, L=large).\\\\",
            "Significance levels: * $p < 0.05$, ** $p < 0.01$, *** $p < 0.001$.",
            "\\end{minipage}",
            "\\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a styled Overleaf table for block-strict pass@k.")
    parser.add_argument("--results-dir", default="evaluation/results/eval_1_completed_from_prior")
    parser.add_argument(
        "--output",
        default="evaluation/results/eval_1_completed_from_prior/tables/block_strict_passk_k1_k5_k10_overleaf_styled.tex",
    )
    parser.add_argument(
        "--caption",
        default="Pass@k (\\%) for local context and local context augmented with schema prompting across the four evaluated models.",
    )
    parser.add_argument(
        "--label",
        default="tab:block_strict_passk_docs_vs_snippet",
    )
    parser.add_argument(
        "--stats-csv",
        default="evaluation/results/statistical_test/pairwise_block_strict_wilcoxon_rank_biserial.csv",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    results_dir = root / args.results_dir
    output_path = root / args.output
    stats_path = root / args.stats_csv
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats_by_model = load_pairwise_stats(stats_path)
    rows = build_rows(results_dir, stats_by_model)
    output_path.write_text(render_table(rows, args.caption, args.label), encoding="utf-8")
    print(f"[OK] wrote {output_path}")


if __name__ == "__main__":
    main()
